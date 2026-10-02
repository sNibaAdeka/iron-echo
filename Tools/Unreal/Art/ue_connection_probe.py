"""Read-only probe: run INSIDE Unreal Editor after enabling its Python plugin.

This confirms Python execution in the editor. It does not install a bridge,
connect a remote computer, or verify gameplay/MediaPipe integration.
"""

import unreal


def main():
    project_dir = unreal.Paths.project_dir()
    unreal.log("[IRON_ECHO_PROBE] Python execution is available in Unreal Editor")
    unreal.log("[IRON_ECHO_PROBE] Project directory: " + project_dir)
    unreal.log("[IRON_ECHO_PROBE] This probe did not modify assets or maps")


if __name__ == "__main__":
    main()
