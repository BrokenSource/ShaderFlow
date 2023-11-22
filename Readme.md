👆【☰】Table of Contents

<div align="justify">

<div align="center">
  <img src="https://github.com/BrokenSource/ShaderFlow/assets/29046864/fbd2f3d6-215b-445c-bf66-9067110c33ad" width="230">

  <h1>ShaderFlow</h1>

  <img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fhits.dwyl.com%2FBrokenSource%2FShaderFlow.json%3Fshow%3Dunique&label=Visitors&color=blue"/>
  <img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fhits.dwyl.com%2FBrokenSource%2FShaderFlow.json&label=Page%20Views&color=blue"/>

  The Interactive Shader Renderer Platform

  <sub>🚧 This project is under development, not every branded item is available yet 🚧</sub>

  > The long self-awaited **rewrite** and **rebranding** of [**Modular Music Visualizer**](https://github.com/Tremeschin/ModularMusicVisualizer)
</div>

<!-- mom, get the camera -->
<!-- [![Star History Chart](https://api.star-history.com/svg?repos=BrokenSource/ShaderFlow&type=Date)](https://star-history.com/#BrokenSource/ShaderFlow&Date) -->

<br/>
<br/>

# 🔥 Description
ShaderFlow is a **framework** for creating **real time**, **audio reactive** shaders easily

Imagine [**ShaderToy**](https://www.shadertoy.com), but with a similar architecture as [**Manim**](https://github.com/3b1b/manim), that's **ShaderFlow** 🔥

A complete **Tool** for **CGI Artists** and **Musicians** to create videos, live performances

- **Second Order Systems**: Bring soul to your shaders with physics-like animations
- **Create and render** shaders easily, explore them with an interactive window
- **Camera2D, Camera3D**: Use 2D or 3D cameras to explore your scene
- **No Watermarks**: Non intrusive experience, we trust the user
- **Configurable**: Make your own complex pipeline and shaders
- **Timeline**: Animate your shaders with easy keyframes
- **Audio Reactive**: Use music to drive the visuals
- **360° Videos**: Render shaders to 360° videos
- **Live music**: Real time professional video
- **Cross Platform**: Windows, Linux and MacOS
- **Open Source**: Trust and transparency

The **possibilities** are **limitless**, create anything with math or use **quality presets**

<sub>Ideally, this project shall be rewritten in Rust in the future, I'm willing to learn it or fund someone to do it if it's ever successful.</sub>


<br/>
<br/>

# 📦 Installation

## 🪛 Running from the Source Code
**ShaderFlow**, similar to [Manim](https://github.com/3b1b/manim), is better used directly from source code for direct control on the complex pipeline

Follow instructions on our [**Monorepo**](https://github.com/BrokenSource/BrokenSource) for downloading our Framework, then continue here

- **Scene files** are placed under `Scenes/*.py`

Simply run `broken shaderflow` to see all available scenes

And `broken shaderflow (scene)` to run a specific scene


<br/>

## 🔮 Prebuilt Binaries
Whenever stuff gets more stable, we'll likely release pypi packages so you can just `pip install shaderflow` and run it directly from the source code or prebuilt binaries that you can just download and run `./shaderflow scene.py`


<br/>
<br/>

# 🚧 Hardware Requirements
Highly depends on the shader and number of audio or video inputs
- **CPU:** Any<sup>C1</sup> with a decent single-core performance<sup>C2</sup>
- **GPU:** Any<sup>G1,G2</sup> that supports OpenGL 3.3+ and has non zero VRAM (128MB+ free)
- **OS:** Any<sup>O1</sup>, Windows (10+), Linux, macOS
- **RAM:** Depends on the mode:
  - **Realtime**: Minimum 200 MB available, plus 500 MB per 1080p video as texture
  - **Rendering**: Realtime + 650 MB per hour of audio + 2 GB per 1080p video<sup>R1</sup>

<br/>

**Footnotes:**

<sub><b>*C1,G1:</b> <i>Affects realtime-able framerates and encoding times, any entry level desktop should be able to do 60 FPS</i></sub>
<br/>
<sub><b>*C2</b> <i>Audio DSP is the main overhead, on a Ryzen 9 5900x I was able to render at 1600 FPS the Spectrogram only Scene</i></sub>
<br/>
<sub><b>*G2:</b> <i>Depends on the shader you want to run, some are intensive. Scales quadratically with resolution</i></sub>
<br/>
<sub><b>*O1:</b> <i>Requires supporting to run the current latest Python version</i></sub>
<br/>
<sub><b>*R1:</b> <i>A 4k video will take roughly 4x the RAM of a 1080p video on FFmpeg to render</i></sub>


<br/>
<br/>

# ❓ Questions, Trivia, FAQ

- **Q:** Why to even Open Source such an ambitious project?

**A:** I'm an autotelic person. This software is a tool I would use myself and prefer it to be _"hackable"_ and Open Source. In plain terms, I want to do something great that lasts, and optimally be the best choice for the job. I am primarily motivated by the possibilities of what the Community members can do with it, I hugely expect the contributions back and am thinking on how we can both grow together.


<br/>
<br/>

# ⚖️ License
We deeply trust the user and community by being **Open Source**, but there is no free lunch

- 💝 Projects takes many human-hours to be created, consider retributing the favor by **donating** if you can or made money with them, do **share** the projects with others

- 💰 We are **not** against **Commercial** use, but we are against **abuse** of the projects and their code. Be fair, get in touch with us and we'll be happy to help both sides grow


## 👤 Personal use
- **User Generated Content**: CC-BY 4.0 License
- **Code**: AGPLv3-Only License

While we won't enforce punishments for failed attributions, we would appreciate if you could credit us

## 🎩 Professional use
Want to use this for your company or comercially?

- Let's do something great together, contact us at [Broken Source Software](https://github.com/BrokenSource)

</div>