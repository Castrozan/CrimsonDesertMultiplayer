#include "mod/agent/agent_bridge.h"

#include <algorithm>
#include <cmath>

#include "common/keys.h"
#include "mod/agent/agent_server.h"
#include "mod/game/actor_lookup.h"
#include "mod/game/camera_reader.h"
#include "mod/game/player_reader.h"

namespace cdmp::agent {

namespace {

constexpr float kActorRadiusMetres = 60.0f;
constexpr size_t kMaxActors = 16;
constexpr uint64_t kMaxVelocityIntervalMs = 2000;

bool is_character_key(uint32_t key) { return (key >> 24) == 0xA0 || (key >> 24) == 0xB0; }

std::string_view actor_kind(uint32_t key) {
    if (net::keys::is_mod_key(key)) return "coop_copy";
    return (key >> 24) == 0xA0 ? "player" : "character";
}

std::vector<ActorView> actors_near(const proto::Vec3& centre) {
    std::vector<ActorView> actors;
    for (const uint32_t key : game::actor_keys()) {
        if (!is_character_key(key)) continue;
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

class GameStateSource {
public:
    explicit GameStateSource(bool in_game) : in_game_(in_game), started_ms_(GetTickCount64()) {
        if (!in_game_) return;
        player_reader_.init();
        camera_reader_.init();
    }

    AgentState sample() {
        AgentState state;
        state.sequence = ++sequence_;
        state.uptime_ms = GetTickCount64() - started_ms_;
        if (!in_game_) {
            state.player_status = "not running inside the game";
            state.camera_status = state.player_status;
            return state;
        }
        if (auto snapshot = player_reader_.read()) {
            state.player = PlayerView{snapshot->position, snapshot->rotation, snapshot->health,
                                      snapshot->health_max, snapshot->stamina, snapshot->stamina_max,
                                      snapshot->static_pos_error};
            state.player_status = "in world";
            const uint64_t now_ms = GetTickCount64();
            if (last_position_ && now_ms > last_position_ms_ && now_ms - last_position_ms_ <= kMaxVelocityIntervalMs) {
                const float seconds = static_cast<float>(now_ms - last_position_ms_) / 1000.0f;
                state.velocity = proto::Vec3{(snapshot->position.x - last_position_->x) / seconds,
                                             (snapshot->position.y - last_position_->y) / seconds,
                                             (snapshot->position.z - last_position_->z) / seconds};
            }
            last_position_ = snapshot->position;
            last_position_ms_ = now_ms;
            state.actors = actors_near(snapshot->position);
        } else {
            state.player_status = player_reader_.last_failure();
        }
        if (auto camera = camera_reader_.read()) {
            state.camera = CameraView{camera->position, camera->forward, camera->right};
            state.camera_status = "ok";
        } else {
            state.camera_status = camera_reader_.last_failure();
        }
        return state;
    }

private:
    bool in_game_;
    uint64_t started_ms_;
    uint64_t sequence_ = 0;
    std::optional<proto::Vec3> last_position_;
    uint64_t last_position_ms_ = 0;
    game::PlayerReader player_reader_;
    game::CameraReader camera_reader_;
};

}  // namespace

void run_bridge(uint16_t port, HANDLE stop_event, bool in_game) {
    GameStateSource source(in_game);
    serve(port, stop_event, [&source] { return source.sample(); });
}

}  // namespace cdmp::agent
