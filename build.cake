using Cake.Core.IO;
using Cake.Common.Diagnostics;
using Cake.Common.Tools.DotNet;

#addin "nuget:?package=Cake.Npm&version=5.1.0"
#load "./build/AssemblyPublicizerTool.cake"

var target = Argument("target", "Build");
var configuration = Argument("configuration", "Release");

var tempDir = System.IO.Path.GetTempPath();
var websocketSourceRoot = "/opt/websocket-sharp-src";
var websocketSourceProject = $"{websocketSourceRoot}/websocket-sharp/websocket-sharp.csproj";
var websocketBuildPath = System.IO.Path.Combine(tempDir, "websocket-sharp-build");
var websocketIntermediatePath = System.IO.Path.Combine(websocketBuildPath, "obj");
var websocketAssemblyPath = System.IO.Path.Combine(websocketBuildPath, "websocket-sharp.dll");
var websocketCommit = "4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1";

int RunCheckedBuildCommand(string stepName, string command)
{
    return StartProcess("/bin/bash", new ProcessSettings
    {
        Arguments = $"scripts/run-build-step.sh \"{stepName}\" {command}"
    });
}

var publicizerInputPath = "./libs/valheim/";
var publicizerOutputPath = publicizerInputPath;

if (DirectoryExists("/opt/steam/libs"))
{
    publicizerInputPath = "/opt/steam/libs/";
    publicizerOutputPath = tempDir;
}

var assembliesToPublicize = new[]
{
    new { Input = $"{publicizerInputPath}assembly_utils.dll",   Output = $"{publicizerOutputPath}assembly_utils.public.dll" },
    new { Input = $"{publicizerInputPath}assembly_valheim.dll", Output = $"{publicizerOutputPath}assembly_valheim.public.dll" }
};

Task("Clean")
    .Does(() =>
{
    DotNetClean("./WebMap/WebMap.csproj", new DotNetCleanSettings
    {
        Configuration = configuration,
    });

    CleanDirectory($"./WebMap/obj");
    DeleteFiles("./WebMap/web/main.js");
    if (DirectoryExists(websocketBuildPath))
    {
        CleanDirectory(websocketBuildPath);
    }
    foreach (var asm in assembliesToPublicize)
    {
      DeleteFiles(asm.Output);
    }
});

Task("Publicize")
    .Does((context) =>
{
    var publicizer = new AssemblyPublicizerTool(context);

    foreach (var asm in assembliesToPublicize)
    {
        var inputFile = context.FileSystem.GetFile(asm.Input);
        var outputFile = context.FileSystem.GetFile(asm.Output);

        bool needsPublicizing = !outputFile.Exists ||
            System.IO.File.GetLastWriteTimeUtc(outputFile.Path.FullPath) < System.IO.File.GetLastWriteTimeUtc(inputFile.Path.FullPath);

        if (needsPublicizing)
        {
            publicizer.Publicize(asm.Input, asm.Output);
        }
        else
        {
            context.Information($"Skipping publicize for {asm.Input} (already up-to-date).");
        }
    }
});

Task("BuildWebsocketSharp")
    .Does((context) =>
{
    var commitFile = System.IO.Path.Combine(websocketSourceRoot, ".upstream-commit");
    if (!System.IO.File.Exists(websocketSourceProject) ||
        !System.IO.File.Exists(commitFile) ||
        System.IO.File.ReadAllText(commitFile).Trim() != websocketCommit)
    {
        throw new Exception("Verified websocket-sharp source tree is missing or has the wrong commit.");
    }

    EnsureDirectoryExists(websocketBuildPath);
    CleanDirectory(websocketBuildPath);
    EnsureDirectoryExists(websocketIntermediatePath);
    var sourceBuildExitCode = RunCheckedBuildCommand(
        "websocket source xbuild",
        $"xbuild \"{websocketSourceProject}\" /target:Rebuild /property:Configuration=Release /property:OutputPath=\"{websocketBuildPath}/\" /property:BaseIntermediateOutputPath=\"{websocketIntermediatePath}/\" /property:IntermediateOutputPath=\"{websocketIntermediatePath}/\" /verbosity:minimal"
    );
    if (sourceBuildExitCode != 0 || !System.IO.File.Exists(websocketAssemblyPath) || new System.IO.FileInfo(websocketAssemblyPath).Length == 0)
    {
        throw new Exception("Canonical websocket-sharp source build failed.");
    }
    context.Information($"Built websocket-sharp from verified commit {websocketCommit} at {websocketAssemblyPath}.");
});

var BuildTask = Task("Build")
    .Does(() =>
{
    var webMapBuildExitCode = RunCheckedBuildCommand(
        "WebMap dotnet build",
        $"dotnet build \"./WebMap/WebMap.csproj\" --configuration \"{configuration}\""
    );
    if (webMapBuildExitCode != 0)
    {
        throw new Exception("WebMap managed build failed.");
    }

    if (configuration == "Release")
    {
        var packageExitCode = RunCheckedBuildCommand(
            "release packager",
            $"node scripts/package-release.js WebMap/bin/Release/net48 WebMap/web THIRD-PARTY-NOTICES.txt \"{websocketAssemblyPath}\""
        );
        if (packageExitCode != 0)
        {
            throw new Exception("Canonical four-file release packaging failed.");
        }

        var inspectionExitCode = RunCheckedBuildCommand(
            "release privacy inspector",
            "bash scripts/inspect-release-privacy.sh"
        );
        if (inspectionExitCode != 0)
        {
            throw new Exception("Release privacy inspection failed.");
        }
    }
});

if (HasArgument("rebuild")) {
    BuildTask.IsDependentOn("Clean");
}
BuildTask.IsDependentOn("Publicize");
BuildTask.IsDependentOn("BuildWebsocketSharp");
BuildTask.IsDependentOn("BuildNpm");

Task("BuildNpm").Does(() => {
    var settings = new NpmInstallSettings();

    settings.LogLevel = NpmLogLevel.Info;
    settings.WorkingDirectory = "./";
    settings.Production = true;

    NpmInstall(settings);

    if (configuration.Equals("Debug"))
    {
        NpmRunScript("build-dev");
    }
    else
    {
        NpmRunScript("build");
    }
});

RunTarget(target);
