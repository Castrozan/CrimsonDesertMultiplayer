#pragma once

#include <cstdint>

namespace cdmp::status::build_3663 {

inline constexpr uint32_t kActor_Components = 0x68;
inline constexpr uint32_t kComponents_Status = 0x20;
inline constexpr uint32_t kStatus_HideFlags = 0x3B8;
inline constexpr uint32_t kStatus_HideFlagsMore = 0x3C0;
inline constexpr uint64_t kHideFlag_LoginPending = 0x2;
inline constexpr uint64_t kHideFlag_Spawn = 0x100000;

inline uint64_t hide_flags(uintptr_t status) {
    return *reinterpret_cast<const uint64_t*>(status + kStatus_HideFlags);
}

inline uint64_t hide_flags_more(uintptr_t status) {
    return *reinterpret_cast<const uint64_t*>(status + kStatus_HideFlagsMore);
}

}  // namespace cdmp::status::build_3663
