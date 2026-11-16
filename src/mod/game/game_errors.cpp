#include "mod/game/game_errors.h"

#include <windows.h>

#include <cstdint>
#include <cstring>
#include <map>
#include <string>

#include <safetyhook.hpp>

#include "mod/game/offsets.h"
#include "mod/game/safe_memory.h"
#include "mod/log.h"

namespace cdmp::game {
namespace {
namespace off = build_3663;

// Entry of the logger: arguments 10-13 on the stack ([rsp] = return address).
// Seen at a call site (0x3A8145..0x3A8184): arg10 dword = code, arg11 dword =
// severity, arg12 = const char* message (printf format), arg13 = first value.
constexpr uintptr_t kErrorLogger = 0x3AACB0;
constexpr uint8_t kErrorLoggerHead[] = {0x48};
constexpr uint32_t kArgCode = 0x50, kArgSeverity = 0x58, kArgText = 0x60, kArgValue = 0x68;
constexpr int kExtraValues = 3;  // arguments 14-16 (more format values, if any)

struct Entry {
    uintptr_t caller;
    uint32_t code;
    uint32_t severity;
    uint64_t value;
    uint64_t extra[kExtraValues];
    char text[160];
};
SafetyHookMid g_hook;
SRWLOCK g_lock = SRWLOCK_INIT;
Entry g_ring[32];
uint32_t g_count = 0;
uint64_t g_lost = 0;
uintptr_t g_base = 0;

bool copy_entry(uint64_t rsp, Entry& e) {
    __try {
        e.caller = *reinterpret_cast<const uintptr_t*>(rsp);
        e.code = *reinterpret_cast<const uint32_t*>(rsp + kArgCode);
        e.severity = *reinterpret_cast<const uint32_t*>(rsp + kArgSeverity);
        e.value = *reinterpret_cast<const uint64_t*>(rsp + kArgValue);
        for (int k = 0; k < kExtraValues; ++k) {
            e.extra[k] = *reinterpret_cast<const uint64_t*>(rsp + kArgValue + 8 + 8 * k);
        }
        const char* text = *reinterpret_cast<const char* const*>(rsp + kArgText);
        size_t i = 0;
        if (text) {
            for (; i + 1 < sizeof e.text && text[i]; ++i) e.text[i] = text[i];
        }
        e.text[i] = '\0';
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

void on_error(safetyhook::Context& ctx) {
    Entry e;
    if (!copy_entry(ctx.rsp, e)) return;
    if (!TryAcquireSRWLockExclusive(&g_lock)) {
        ++g_lost;
        return;
    }
    if (g_count < 32) g_ring[g_count++] = e;
    else ++g_lost;
    ReleaseSRWLockExclusive(&g_lock);
}

}  // namespace

bool game_errors_install() {
    if (g_hook) return true;
    g_base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    uint8_t head[1];
    if (g_base != off::kImageBase || !safe_read(g_base + kErrorLogger, head, 1) || head[0] != kErrorLoggerHead[0]) {
        log::warn("Game errors: logger not recognised; not hooked");
        return false;
    }
    auto* target = reinterpret_cast<uint8_t*>(g_base + kErrorLogger);
    auto direct = safetyhook::MidHook::create(target, on_error);
    if (direct) {
        g_hook = std::move(*direct);
        log::info("Game errors: hook installed (the game's internal errors go to this log)");
        return true;
    }
    log::warn("Game errors: hook not possible (safetyhook error {}); not hooked", static_cast<int>(direct.error().type));
    return false;
}

void game_errors_drain() {
    if (!g_hook) return;
    Entry local[32];
    uint32_t n = 0;
    uint64_t lost = 0;
    AcquireSRWLockExclusive(&g_lock);
    n = g_count;
    std::memcpy(local, g_ring, sizeof(Entry) * n);
    g_count = 0;
    lost = g_lost;
    ReleaseSRWLockExclusive(&g_lock);

    static std::map<std::string, int> seen;
    static uint64_t logged = 0, reported_lost = 0;
    for (uint32_t i = 0; i < n; ++i) {
        const Entry& e = local[i];
        const uintptr_t rva = e.caller >= g_base ? e.caller - g_base : e.caller;
        const std::string id = std::to_string(rva) + "|" + e.text;
        if (logged >= 400 || ++seen[id] > 10) continue;  // each distinct error up to 10 times
        ++logged;
        log::info("Game error: \"{}\" (values 0x{:X} 0x{:X} 0x{:X} 0x{:X}, code {}, severity {}, from exe+0x{:X})",
                  e.text, e.value, e.extra[0], e.extra[1], e.extra[2], e.code, e.severity, rva);
    }
    if (lost != reported_lost) {
        log::info("Game errors: {} not copied (busy)", lost);
        reported_lost = lost;
    }
}

}  // namespace cdmp::game
