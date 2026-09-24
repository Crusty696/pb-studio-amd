using System.Threading;
using System.Threading.Tasks;

namespace PBStudio.UI.Services;

/// <summary>Optionaler Vertrag fuer exklusive LLM-Provider-Umschaltung.</summary>
public interface IProviderSelectionApi
{
    Task<bool> SelectProviderAsync(string provider, CancellationToken ct = default);
}
