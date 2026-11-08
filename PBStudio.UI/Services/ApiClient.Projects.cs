using System.Collections.Concurrent;
using System.IO;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Models;

namespace PBStudio.UI.Services;

public partial class ApiClient
{
    // --- Project ---

    public async Task<ProjectInfo?> CreateProjectAsync(string name, string path)
    {
        var project = await PostAsync<ProjectInfo>(
            "/project/create",
            new { name, path }).ConfigureAwait(false);
        if (project is not null)
            SetActiveProjectIdentity(project);
        return project;
    }

    public async Task<ProjectInfo?> OpenProjectAsync(string path)
    {
        var project = await PostAsync<ProjectInfo>(
            "/project/open",
            new { path }).ConfigureAwait(false);
        if (project is not null)
            SetActiveProjectIdentity(project);
        return project;
    }

    public async Task<StatusResponse?> SaveProjectAsync()
        => await PostAsync<StatusResponse>("/project/save", null).ConfigureAwait(false);

    public async Task<StatusResponse?> CloseProjectAsync()
    {
        var result = await PostAsync<StatusResponse>(
            "/project/close",
            null).ConfigureAwait(false);
        if (result is not null)
            ResetActiveProjectIdentity();
        return result;
    }

    /// <summary>
    /// Laedt die manuellen Anker des aktiven Projekts.
    /// Audit 2026-08-06 (T4.3): neu, der ANCHOR-Tab hatte kein Backend.
    /// </summary>
    public Task<AnchorListResponse?> GetProjectAnchorsAsync(CancellationToken ct = default)
        => GetAsync<AnchorListResponse>("/project/anchors", ct);

    /// <summary>Ersetzt die manuellen Anker des aktiven Projekts.</summary>
    public Task<AnchorListResponse?> SetProjectAnchorsAsync(
        List<AnchorEntry> anchors,
        CancellationToken ct = default)
        => PostAsync<AnchorListResponse>("/project/anchors", anchors, ct);

    public async Task<ProjectInfo?> GetProjectInfoAsync()
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, "/project/info");

        try
        {
            using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, _shutdownCts.Token).ConfigureAwait(false);
            if (response.StatusCode == System.Net.HttpStatusCode.BadRequest)
            {
                var detail = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (detail.Contains("Kein Projekt geöffnet", StringComparison.OrdinalIgnoreCase)
                    || detail.Contains("Kein Projekt ge\u00f6ffnet", StringComparison.OrdinalIgnoreCase))
                {
                    ResetActiveProjectIdentity();
                    return null;
                }
            }

            response.EnsureSuccessStatusCode();
            var project = await response.Content.ReadFromJsonAsync<ProjectInfo>(JsonOptions).ConfigureAwait(false);
            if (project is not null)
                SetActiveProjectIdentity(project);
            return project;
        }
        catch (Exception ex) when (IsExpectedCancellation(ex))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "GET {Url} fehlgeschlagen", "/project/info");
            return null;
        }
    }

    private void SetActiveProjectIdentity(ProjectInfo project)
    {
        var projectPath = project.Path.Trim();
        try
        {
            projectPath = Path.GetFullPath(projectPath);
        }
        catch (Exception ex) when (ex is ArgumentException
                                   or NotSupportedException
                                   or PathTooLongException)
        {
            _logger.LogWarning(
                ex,
                "Projektpfad konnte fuer Feedback-Idempotenz nicht normalisiert werden: {Path}",
                project.Path);
        }

        projectPath = Path.TrimEndingDirectorySeparator(projectPath)
            .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar)
            .ToUpperInvariant();
        Volatile.Write(ref _activeProjectIdentity, $"path:{projectPath}");
    }

    private void ResetActiveProjectIdentity()
        => Volatile.Write(
            ref _activeProjectIdentity,
            $"session:{Guid.NewGuid():N}");
}
