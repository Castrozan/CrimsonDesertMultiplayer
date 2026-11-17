#pragma once

#include <cstdint>
#include <vector>

#include "common/protocol.h"
#include "mod/agent/agent_state.h"

namespace cdmp::agent {

class NearbyActors {
public:
    std::vector<ActorView> around(const proto::Vec3& centre, uint64_t now_ms);

private:
    std::vector<uint32_t> character_keys_;
    uint64_t keys_listed_ms_ = 0;
    bool keys_listed_ = false;
};

}  // namespace cdmp::agent
