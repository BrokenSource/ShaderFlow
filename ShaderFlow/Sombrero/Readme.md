<div align="justify">

<div align="center">
  <h1>Sombrero</h1>

  A pun about Shadows
</div>
<br>
<br>

# 🌵 Description
> Sombrero is the Shader Engine for ShaderFlow

A Game Engine-like messaging system on a fully Modular and complex Node-Graph structure

<br>
<br>

# 👷‍♂️ Architecture
The **most important files** to study and understand are:

- [**SombreroModule**](./SombreroModule.py): A standard that defines the complex relationship between Modules

- [**SombreroEngine**](./SombreroEngine.py): _Defines_ the rendering pipeline and contains most ModernGL objects

- [**SombreroTexture**](./Modules/SombreroTexture.py): A wrapper around `ModernGL.Texture` to automate the boring stuff

- [**SombreroShader**](./Modules/SombreroShader.py): A Smart GLSL Shader metaprogramming (code that writes code)

- [**SombreroContext**](./Modules/SombreroContext.py): Stores the basic state of the scene such as time, resolution and window

<br>
<br>

## 🌐 **Super** Node Graph
The way Sombrero deals with modules relationship is by a Node Graph structure.

<br>

**Basic Definitions**:

- **Pipeline**: A set of ShaderVariables that are sent to the shader, the _output_ of modules
- **Node**: A SombreroModule with some internal state and pipeline, updated every frame
- **Edge**: A directed connection between two nodes, also the pipeline flow direction
- **Super Node**: A group of nodes that are virtually _"on the same node"_

</div>