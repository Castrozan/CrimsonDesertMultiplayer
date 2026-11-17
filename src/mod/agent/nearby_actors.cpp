#include "mod/agent/nearby_actors.h"

#include <algorithm>
#include <cmath>
#include <string_view>

#include "mod/game/actor_lookup.h"
#include "common/keys.h"

namespace cdmp::agent {
namespace {

constexpr float kActorRadiusMetres = 60.0f;
constexpr size_t kMaxActors = 16;
constexpr uint64_t kKeyListLifetimeMs = 1000;

bool is_character_key(uint32_t key) { return (key >> 24) == 0xA0 || (key >> 24) == 0xB0; }

std::string_view actor_kind(uint32_t key) {
    if (net::keys::is_mod_key(key)) return "coop_copy";
    return (key >> 24) == 0xA0 ? "player" : "character";
}

}  // namespace

std::vector<ActorView> NearbyActors::around(const proto::Vec3& centre, uint64_t now_ms) {
    if (!keys_listed_ || now_ms - keys_listed_ms_ >= kKeyListLifetimeMs) {
        character_keys_ = game::actor_keys();
        std::erase_if(character_keys_, [](uint32_t key) { return !is_character_key(key); });
        keys_listed_ms_ = now_ms;
        keys_listed_ = true;
    }
    std::vector<ActorView> actors;
    for (const uint32_t key : character_keys_) {
        const auto position = game::actor_world_position(key);
        if (!position) continue;
        const float distance = std::hypot(position->x - centre.x, position->y - centre.y, position->z - centre.z);
        if (distance < 0.05f || distance > kActorRadiusMetres) continue;
        actors.push_back(ActorView{key, actor_kind(key), *position, distance});
    }
    std::sort(actors.begin(), actors.end(),
              [](const ActorView& a, const ActorView& b) { return a.distance < b.distance; });
    if (actors.size() > kMaxActors) actors.resize(kMaxActors);
    return actors;
}

}  // namespace cdmp::agent
