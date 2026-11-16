#pragma once

#include <windows.h>

#include <cstdint>
#include <functional>

#include "mod/agent/agent_state.h"

namespace cdmp::agent {

using StateProvider = std::function<AgentState()>;

void serve(uint16_t port, HANDLE stop_event, const StateProvider& provide_state);

}  // namespace cdmp::agent
