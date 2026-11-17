#include "mod/agent/agent_bridge.h"

#include <cmath>

#include "mod/agent/agent_server.h"
#include "mod/agent/nearby_actors.h"
#include "mod/game/camera_reader.h"
#include "mod/game/player_reader.h"
#include "mod/net/remote_puppet.h"

namespace cdmp::agent {

namespace {

constexpr uint64_t kMaxVelocityIntervalMs = 2000;

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
        state.paused = net::puppet_local_paused();
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
            state.actors = nearby_actors_.around(snapshot->position, now_ms);
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
    NearbyActors nearby_actors_;
};

}  // namespace

void run_bridge(uint16_t port, HANDLE stop_event, bool in_game) {
    GameStateSource source(in_game);
    serve(port, stop_event, [&source] { return source.sample(); });
}

}  // namespace cdmp::agent
