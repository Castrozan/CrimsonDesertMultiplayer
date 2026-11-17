#include "mod/puppet/visibility.h"

#include <windows.h>

#include <atomic>
#include <cstdint>
#include <cstring>
#include <optional>

#include "mod/game/actor_lookup.h"
#include "mod/game/safe_memory.h"
#include "mod/log.h"

namespace cdmp::puppet {
namespace {

namespace build_3663 {
inline constexpr uint32_t kActor_Components = 0x68;
inline constexpr uint32_t kComponents_Status = 0x20;
inline constexpr uint32_t kStatus_HideFlags = 0x3B8;
inline constexpr uint64_t kHideFlag_Spawn = 0x100000;
inline constexpr uintptr_t kSetStatusHideFlag = 0x1932980;
inline constexpr uint8_t kSetStatusHideFlagHead[] = {0x48, 0x8B, 0xC4, 0x48, 0x89, 0x58, 0x10, 0x48,
                                                     0x89, 0x68, 0x18, 0x48, 0x89, 0x70, 0x20, 0x57};
}  // namespace build_3663

constexpr uint32_t kPuppetPlayerKey = 0xA010F001;
constexpr uint64_t kCheckIntervalMs = 250;

using SetStatusHideFlag = void(__fastcall*)(uintptr_t status, uint32_t flag, bool set, float fade_seconds,
                                            bool immediate);

enum class SetterState { Unresolved, Recognised, Unrecognised };

std::atomic<SetterState> g_setter_state{SetterState::Unresolved};
std::atomic<bool> g_unrecognised_logged{false};
std::atomic<uint64_t> g_cleared_flags{0};

SetStatusHideFlag resolve_setter() {
    const auto base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    uint8_t head[sizeof build_3663::kSetStatusHideFlagHead];
    const bool recognised = game::safe_read(base + build_3663::kSetStatusHideFlag, head, sizeof head) &&
                            std::memcmp(head, build_3663::kSetStatusHideFlagHead, sizeof head) == 0;
    g_setter_state = recognised ? SetterState::Recognised : SetterState::Unrecognised;
    return recognised ? reinterpret_cast<SetStatusHideFlag>(base + build_3663::kSetStatusHideFlag) : nullptr;
}

std::optional<uintptr_t> puppet_status() {
    const auto actor = game::find_actor(kPuppetPlayerKey);
    if (!actor) return std::nullopt;
    const auto components = game::read_ptr(*actor + build_3663::kActor_Components);
    if (!components || !*components) return std::nullopt;
    const auto status = game::read_ptr(*components + build_3663::kComponents_Status);
    if (!status || !*status) return std::nullopt;
    return status;
}

}  // namespace

void visibility_on_game_network_thread() {
    static uint64_t checked_at = 0;
    const uint64_t now = GetTickCount64();
    if (now - checked_at < kCheckIntervalMs) return;
    checked_at = now;
    static const SetStatusHideFlag setter = resolve_setter();
    if (!setter) return;
    const auto status = puppet_status();
    if (!status) return;
    const auto flags = game::read<uint64_t>(*status + build_3663::kStatus_HideFlags);
    if (!flags || !(*flags & build_3663::kHideFlag_Spawn)) return;
    setter(*status, static_cast<uint32_t>(build_3663::kHideFlag_Spawn), false, 0.0f, false);
    g_cleared_flags = *flags;
}

void visibility_log_tick() {
    if (g_setter_state == SetterState::Unrecognised && !g_unrecognised_logged.exchange(true)) {
        log::warn("Puppet visibility: status flag setter not recognised; the copy stays hidden");
    }
    if (const uint64_t flags = g_cleared_flags.exchange(0)) {
        log::info("Puppet visibility: cleared the spawn hide flag (flags were 0x{:X})", flags);
    }
}

}  // namespace cdmp::puppet
