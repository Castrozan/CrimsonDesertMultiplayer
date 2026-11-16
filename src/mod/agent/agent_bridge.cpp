#include "mod/agent/agent_bridge.h"

#include "mod/agent/agent_server.h"
#include "mod/game/camera_reader.h"
#include "mod/game/player_reader.h"

namespace cdmp::agent {

namespace {

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
    game::PlayerReader player_reader_;
    game::CameraReader camera_reader_;
};

}  // namespace

void run_bridge(uint16_t port, HANDLE stop_event, bool in_game) {
    GameStateSource source(in_game);
    serve(port, stop_event, [&source] { return source.sample(); });
}

}  // namespace cdmp::agent
