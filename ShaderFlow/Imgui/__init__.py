from Broken import block_modules

# Faster imgui_bundle import
with block_modules("matplotlib"):
    import imgui_bundle

from imgui_bundle import imgui

from ShaderFlow.Imgui.Integration import ModernglWindowRenderer