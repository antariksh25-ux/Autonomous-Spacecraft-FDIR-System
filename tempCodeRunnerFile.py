@app.post("/mission-phase", summary="Change the current mission phase (affects ethical decisions)")
# def set_mission_phase(req: MissionPhaseRequest):
#     """
#     §5.6, §6.1: Changes mission phase. This directly affects ethical engine decisions.
#     During CRITICAL_MANEUVER — all autonomous action is blocked regardless of confidence.
#     """
#     valid_phases = set(cfg.MISSION_PHASE_CRITICALITY.keys())
#     if req.phase not in valid_phases:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Invalid phase. Must be one of: {valid_phases}"
#         )
#     cfg.MISSION_PHASE = req.phase
#     criticality = cfg.MISSION_PHASE_CRITICALITY[req.phase]
#     with state_lock:
#         system_state["mission_phase"]     = req.phase
#         system_state["mission_criticality"] = criticality
#     return {
#         "status":      "updated",
#         "phase":       req.phase,
#         "criticality": criticality,
#         "message":     f"Mission phase set to '{req.phase}' (criticality: {criticality})",
#     }


# @app.post("/reset", summary="Full system reset — clears all state and restarts from nominal")
# def reset_system():
#     """Resets simulator, monitors, logs, and all internal state to nominal."""
#     reset_signal.set()
#     return {"status": "reset_queued", "message": "System reset will complete at next tick"}

