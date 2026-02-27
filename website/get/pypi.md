---
title: Package
icon: material/language-python
---

## Dependency

Simply add or install the [`shaderflow`](https://pypi.org/project/shaderflow/) package to your project or environment:

=== ":simple-astral: uv"
    ```sh linenums="1"
    uv add shaderflow
    ```
=== ":simple-toml: pyproject.toml"
    ```toml linenums="1"
    [project]
    dependencies = ["shaderflow", ...]
    ```
=== ":simple-python: pip"
    ```sh linenums="1"
    pip install shaderflow
    ```

After syncing dependencies, run `shaderflow` or import it in scripts!

!!! tip "Suggestions"
    - Pin the version `shaderflow==x.y.z` for stability

## Direct

Following the concepts of [uv](https://docs.astral.sh/uv/) • [tools](https://docs.astral.sh/uv/guides/tools/), run with:

```sh title="Command" linenums="1"
# Always latest version
uvx shaderflow (...)

# Specific version
uvx shaderflow@0.10.0 (...)
```
