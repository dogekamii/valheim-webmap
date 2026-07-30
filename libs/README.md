External requirements:

1. Extract the current release of [BepInEx](https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.2/BepInEx_win_x64_5.4.23.2.zip)
   to this directory and rename it to `BepInEx`.
2. Create a directory named `valheim` and copy these files from your Valheim
   installation into it:
   ```
   assembly_utils.dll
   assembly_valheim.dll
   Mono.Security.dll
   UnityEngine.CoreModule.dll
   UnityEngine.dll
   UnityEngine.ImageConversionModule.dll
   UnityEngine.JSONSerializeModule.dll
   ```
3. Publicize the utils and Valheim assemblies. From the project root:
   ```
   dotnet tool restore
   dotnet cake --target=Publicize
   ```

`websocket-sharp.dll` is deliberately not vendored here. The canonical Docker
image acquires the immutable, SHA-256-pinned upstream source and `build.cake`
builds the signed .NET 3.5 project before compiling WebMap. See
`docs/DEPENDENCY_PROVENANCE.md` for the exact commit, archive hash, toolchain,
command, identity, and artifact-reporting boundary.
