using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text.RegularExpressions;
using WebMap.Patches;
using BepInEx;
using HarmonyLib;
using UnityEngine;
using static ZRoutedRpc;
using Random = UnityEngine.Random;
using System.Runtime.InteropServices;
using System.Collections;
using System.Dynamic;

namespace WebMap
{
    //This attribute is required, and lists metadata for your plugin.
    //The GUID should be a unique ID for this plugin, which is human readable (as it is used in places like the config). I like to use the java package notation, which is "com.[your name here].[your plugin name here]"
    //The name is the name of the plugin that's displayed on load, and the version number just specifies what version the plugin is.
    [BepInPlugin(GUID, NAME, VERSION)]

    //This is the main declaration of our plugin class. BepInEx searches for all classes inheriting from BaseUnityPlugin to initialize on startup.
    //BaseUnityPlugin itself inherits from MonoBehaviour, so you can use this as a reference for what you can declare and use in your plugin class: https://docs.unity3d.com/ScriptReference/MonoBehaviour.html
    public class WebMap : BaseUnityPlugin
    {
        public const string GUID = "com.github.h0tw1r3.valheim.webmap";
        public const string NAME = "WebMap";
        public const string VERSION = "2.7.3";
