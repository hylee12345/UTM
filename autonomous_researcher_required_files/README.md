# Autonomous Researcher Framework

Closed-loop laboratory automation framework for autonomous experiment planning,
metamaterial specimen design, device bridges, robot workflows, analysis, BO, and
operator-supervised live execution.

## Live GUI Preview

Browser-captured test-mode screens from the active Live GUI renderer:

<table>
  <tr>
    <td width="50%">
      <img src="docs/assets/readme/live-gui-orchestrator-test-mode.png" alt="Live GUI Orchestrator test-mode screen" />
      <br />
      <sub><b>Orchestrator</b> - mission contract, handoff plan, runtime chat, and cycle status.</sub>
    </td>
    <td width="50%">
      <img src="docs/assets/readme/live-gui-design-agent-report.png" alt="Live GUI Design Agent candidate board" />
      <br />
      <sub><b>Design Agent</b> - generated gyroid TPMS candidates, DOE board, and FDM handoff state.</sub>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/assets/readme/live-gui-design-preview-modal.png" alt="Live GUI STL preview modal" />
      <br />
      <sub><b>STL Preview</b> - enlarged generated specimen preview inside the operator report area.</sub>
    </td>
    <td width="50%">
      <img src="docs/assets/readme/live-gui-design-artifacts.png" alt="Live GUI Design artifacts panel" />
      <br />
      <sub><b>Artifacts</b> - runtime files, STL captures, and digital-thread evidence for generated specimens.</sub>
    </td>
  </tr>
</table>

Choose a documentation language:

- [English Guide](README.en.md)
- [한국어 가이드](README.ko.md)

Fast entry points:

- [Documentation Index](docs/README.md)
- [Complete User Manual KR](docs/tutorials/user_manual.ko.md)
- [Complete User Manual EN](docs/tutorials/user_manual.en.md)
- [Closed Loop / Page / Agent Reference](docs/runtime/closed_loop_and_pages_reference.md)
- [UTM Vision Runtime GUI](docs/hardware/utm_vision_runtime_gui.md)
- [Requirements](REQUIREMENTS.md)
- [API Docs](http://localhost:7860/docs)
- [Live GUI](http://localhost:7860/live)
- [Runtime IDE](http://localhost:7860/ide)

The root guides and complete manuals describe the actual repository layout, GUI pages, closed-loop stage flow, agents, runtime modes, operation sequence, troubleshooting, and developer extension rules.

## UTM Vision Runtime

The UTM integration starts the local ROS 2 vision stack from the main GUI and
uses an agent-callable function for time-windowed monitoring.

Runtime control:

```text
Device Workspaces -> UTM Vision Runtime -> Loading
```

API:

```text
GET  /api/equipment/utm-runtime/status
POST /api/equipment/utm-runtime/start
POST /api/equipment/utm-runtime/stop
```

Agent monitoring:

```text
ToolRegistry.call("vision.equipment_cross_check", payload)
  -> observe_utm_state_window(duration_sec=5.0, sample_interval_sec=0.2, minimum_samples=8)
  -> repeated /compression_tester/summary samples
  -> structured UTM state evidence
```

The monitor intentionally fails closed with
`UTM_INSUFFICIENT_TEMPORAL_EVIDENCE` when only one image/sample is available.
See [UTM Vision Runtime GUI](docs/hardware/utm_vision_runtime_gui.md).
