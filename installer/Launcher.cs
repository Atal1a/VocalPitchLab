using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("VocalPitchLab")]
[assembly: AssemblyProduct("VocalPitchLab")]
[assembly: AssemblyDescription("VocalPitchLab desktop launcher")]
[assembly: AssemblyCompany("VocalPitchLab")]
[assembly: AssemblyCopyright("Copyright © 2026 VocalPitchLab contributors")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

internal static class Launcher
{
    [STAThread]
    private static int Main()
    {
        try
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python = Path.Combine(root, "runtime", "pythonw.exe");
            string entry = Path.Combine(root, "launch.py");
            if (!File.Exists(python) || !File.Exists(entry))
                throw new FileNotFoundException("程序文件不完整，请重新安装 VocalPitchLab。");
            var start = new ProcessStartInfo(python, "-I \"" + entry + "\"");
            start.WorkingDirectory = root;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.EnvironmentVariables.Remove("PYTHONHOME");
            start.EnvironmentVariables.Remove("PYTHONPATH");
            using (Process child = Process.Start(start))
            {
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "VocalPitchLab", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
