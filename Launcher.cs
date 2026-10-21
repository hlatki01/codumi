using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("codumi")]
[assembly: AssemblyProduct("codumi")]
[assembly: AssemblyVersion("0.3.0.0")]
[assembly: AssemblyFileVersion("0.3.0.0")]
[assembly: AssemblyDescription("Your little coding companion.")]

internal static class Launcher
{
    private static string Text(bool missingFiles)
    {
        switch (CultureInfo.CurrentUICulture.TwoLetterISOLanguageName)
        {
            case "pt": return missingFiles ? "Extraia toda a pasta do ZIP antes de abrir o codumi." : "Opção desconhecida: ";
            case "es": return missingFiles ? "Extrae toda la carpeta del ZIP antes de abrir codumi." : "Opción desconocida: ";
            case "fr": return missingFiles ? "Extrayez tout le dossier du ZIP avant de lancer codumi." : "Option inconnue : ";
            case "de": return missingFiles ? "Entpacke den gesamten ZIP-Ordner, bevor du codumi öffnest." : "Unbekannte Option: ";
            case "it": return missingFiles ? "Estrai tutta la cartella ZIP prima di aprire codumi." : "Opzione sconosciuta: ";
            default: return missingFiles ? "Extract the entire ZIP folder before opening codumi." : "Unknown option: ";
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string directory = AppDomain.CurrentDomain.BaseDirectory;
        string flags = "";
        foreach (string arg in args)
        {
            if (arg != "--demo" && arg != "--smoke-test")
            {
                MessageBox.Show(Text(false) + arg, "codumi");
                return 1;
            }
            flags += " " + arg;
        }
        try
        {
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = Path.Combine(directory, "runtime", "pythonw.exe");
            start.Arguments = "\"" + Path.Combine(directory, "app.py") + "\"" + flags;
            start.WorkingDirectory = directory;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            using (Process child = Process.Start(start))
            {
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show(Text(true) + "\n\n" + error.Message, "codumi");
            return 1;
        }
    }
}
