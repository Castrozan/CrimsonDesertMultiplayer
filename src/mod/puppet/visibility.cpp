#include "mod/puppet/visibility.h"

#include <windows.h>

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

using SetStatusHideFlag = void(__fastcall*)(uintptr_t status, uint32_t flag, bool set, float fade_seconds,
                                            bool immediate);

SetStatusHideFlag resolve_setter() {
    const auto base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    uint8_t head[sizeof build_3663::kSetStatusHideFlagHead];
    if (!game::safe_read(base + build_3663::kSetStatusHideFlag, head, sizeof head) ||
        std::memcmp(head, build_3663::kSetStatusHideFlagHead, sizeof head) != 0) {
        log::warn("Puppet visibility: status flag setter not recognised; the copy stays hidden");
        return nullptr;
    }
    return reinterpret_cast<SetStatusHideFlag>(base + build_3663::kSetStatusHideFlag);
}

std::optional<uintptr_t> puppet_status(uint32_t puppet_key) {
    const auto actor = game::find_actor(puppet_key);
    if (!actor) return std::nullopt;
    const auto components = game::read_ptr(*actor + build_3663::kActor_Components);
    if (!components || !*components) return std::nullopt;
    const auto status = game::read_ptr(*components + build_3663::kComponents_Status);
    if (!status || !*status) return std::nullopt;
    return status;
}

}  // namespace

void visibility_tick(uint32_t puppet_key) {
    static const SetStatusHideFlag setter = resolve_setter();
    if (!setter) return;
    const auto status = puppet_status(puppet_key);
    if (!status) return;
    const auto flags = game::read<uint64_t>(*status + build_3663::kStatus_HideFlags);
    if (!flags || !(*flags & build_3663::kHideFlag_Spawn)) return;
    setter(*status, static_cast<uint32_t>(build_3663::kHideFlag_Spawn), false, 0.0f, false);
    log::info("Puppet visibility: cleared the spawn hide flag (flags were 0x{:X})", *flags);
}

}  // namespace cdmp::puppet
