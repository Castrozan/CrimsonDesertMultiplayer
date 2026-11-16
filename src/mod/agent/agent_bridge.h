#pragma once

#include <windows.h>

#include <cstdint>

namespace cdmp::agent {

void run_bridge(uint16_t port, HANDLE stop_event, bool in_game);

}  // namespace cdmp::agent
