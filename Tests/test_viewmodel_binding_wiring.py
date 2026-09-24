"""
Binding-Guard fuer WPF-ViewModel-Properties (Audit 2026-08-05, T3b.2).

Warum es diesen Test gibt
-------------------------
Im Projekt ist dreimal derselbe Fehler passiert: eine ``[ObservableProperty]``
wurde im ViewModel gesetzt, aber von keinem XAML-Element gebunden. Der Wert
reiste bis zur UI und versickerte dort. Dokumentiert im CHANGELOG fuer
``BrainViewModel`` und den Timeline-``StatusText``; das Audit 2026-08-05 fand
weitere 27 Faelle, darunter sechs Fortschrittsanzeigen
(``IsDeleting``, ``IsLoadingClips``, ``IsCleaningGpu``) — deshalb bekam der User
bei laufenden Aktionen keinerlei Rueckmeldung.

Der Test kehrt die Beweislast um: **jede** ObservableProperty muss entweder ein
XAML-Binding haben oder hier mit Begruendung eingetragen sein. Eine neue,
unbeabsichtigt ungebundene Property faellt damit sofort auf.

Die Ausnahmenliste ist bewusst als ehrliche Buchfuehrung gestaltet und nicht als
Freibrief: sie unterscheidet Properties, die reine Steuerlogik sind, von solchen,
die ueber einen zusammengesetzten (und selbst gebundenen) Text in die UI kommen,
und von echten Altlasten ohne jede Verwendung.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWMODEL_DIR = REPO_ROOT / "PBStudio.UI" / "ViewModels"
UI_ROOT = REPO_ROOT / "PBStudio.UI"

# ---------------------------------------------------------------------------
# Bewusst ungebundene Properties -> Begruendung.
#
# "Steuerlogik"      = wird nur programmatisch gelesen (CanExecute, Guards,
#                      Zustandsmaschinen). Ein Binding waere sinnlos.
# "via <Property>"   = Wert erreicht die UI ueber einen zusammengesetzten Text,
#                      der selbst gebunden ist. Kein Datenverlust.
# "Altlast"          = keine weitere Verwendung im ViewModel. Kandidat fuer
#                      Entfernung; bis dahin hier sichtbar statt still.
# ---------------------------------------------------------------------------
INTENTIONALLY_UNBOUND: dict[str, str] = {
    "AnchorPoint.Time": "via TimeText; OnTimeChanged benachrichtigt die Anzeige",
    "AnchorPoint.VideoClipId": "Altlast — keine weitere Verwendung im ViewModel",
    "AudioLibraryViewModel.DurationSeconds": "Steuerlogik — Anzeige laeuft ueber AudioClipModel je Zeile",
    "BrainViewModel.IsResetBusy": "Steuerlogik — CanExecute-Bedingung für Reset-Befehle",
    "ChatViewModel.CurrentModel": "Altlast — pro Nachricht wird ModelName gebunden, global redundant",
    "LearningSessionViewModel.IsPlaying": "Steuerlogik — interner Playback-Zustand",
    "LearningSessionViewModel.CurrentIndex": "via CurrentIndexDisplay; LoadCurrentCut benachrichtigt die Anzeige",
    "MainViewModel.IsBackendConnected": "Altlast — gebunden wird IsBackendUnreachable",
    "ModelManagerViewModel.BaseUrl": "via StatusText",
    "ModelManagerViewModel.OllamaAvailable": "Steuerlogik — Provider-Verfuegbarkeit",
    "ModelManagerViewModel.LmStudioAvailable": "Steuerlogik — Provider-Verfuegbarkeit",
    "ModelManagerViewModel.ActiveProvider": "via StatusText",
    "ModelManagerViewModel.SelectedProvider": "Steuerlogik — synchronisiert Providerwahl für Modellkarten",
    "ModelManagerViewModel.IsActive": "Steuerlogik — View Loaded/Unloaded steuert den Refresh-Timer",
    "InstalledModelCardViewModel.HasActiveTasks": "Altlast — keine weitere Verwendung",
    "DownloadProgressViewModel.CompletedBytes": "Altlast — Download-Fortschritt laeuft ueber ProgressText",
    "DownloadProgressViewModel.TotalBytes": "Altlast — Download-Fortschritt laeuft ueber ProgressText",
    "DownloadProgressViewModel.SizeEstimateGb": "via zusammengesetzten Kartentext",
    "ProductionViewModel.AudioPath": "via StatusText und Render-Request",
    "ProductionViewModel.HasProject": "Steuerlogik — CanStartRender",
    "TimelineViewModel.AudioPath": "Steuerlogik — Quelle fuer Waveform-Laden",
    "TimelineViewModel.HorizontalOffset": "Altlast — Scroll-Zustand, nie an ScrollViewer gehaengt",
    "TimelineViewModel.PreviewVideoPath": "Altlast — Preview-Player nicht verdrahtet",
    "VramTelemetryViewModel.TotalObservations": "via StatusText",
    "VramTelemetryViewModel.TotalSuccess": "via StatusText",
    "VramTelemetryViewModel.TotalFailure": "via StatusText",
    "VramTelemetryViewModel.IsActive": "Steuerlogik — View Loaded/Unloaded/IsVisibleChanged steuert Refresh",
    "VramTelemetryModelCardViewModel.HasError": "Altlast — Fehleranzeige bindet LastErrorText mit NullToVisibilityConverter",
    "VideoLibraryViewModel.VideoImportPath": "Steuerlogik — FilePicker schreibt Pfade fuer Import-Request; keine Texteingabe",
}

OBSERVABLE_PROPERTY_PATTERN = re.compile(
    r"\[ObservableProperty\][^;]*?\b_(\w+)\s*(?:=|;)", re.DOTALL
)


def _pascal_case(field_name: str) -> str:
    """``_isDeleting`` -> ``IsDeleting`` (Namenskonvention des MVVM-Generators)."""
    return field_name[0].upper() + field_name[1:] if field_name else field_name


# Runtime roots are assigned in each view's code-behind. DownloadProgressDialog
# currently only declares its intended type at design time; this is a static
# wiring guard, not proof that a view is instantiated by the running app.
VIEW_CONTEXTS = {
    "MainWindow.xaml": "MainViewModel",
    **{f"Views/{name}View.xaml": f"{name}ViewModel" for name in (
        "Anchor", "AudioLibrary", "Brain", "Chat", "Director", "MediaIngest",
        "ModelManager", "Production", "ProjectOverview", "Settings", "Terminal",
        "Timeline", "VideoLibrary", "VramTelemetry",
    )},
    "Views/LearningSessionDialog.xaml": "LearningSessionViewModel",
    "Views/DownloadProgressDialog.xaml": "DownloadProgressViewModel",
}


def _class_members(source: str) -> tuple[set[tuple[str, str]], dict[tuple[str, str], str]]:
    """Attribute each field to its declaring class, including nested classes."""
    # Preserve offsets while masking comments and literals (which can contain
    # braces or apparent declarations). No backend or C# compiler is imported.
    source = re.sub(
        r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/',
        lambda match: " " * len(match[0]), source, flags=re.DOTALL,
    )
    class_starts = {
        match.end() - 1: match[1]
        for match in re.finditer(r"\bclass\s+(\w+)[^;{}]*\{", source)
    }
    stack: list[str | None] = []
    owners: dict[int, str | None] = {}
    for index, character in enumerate(source):
        if character == "{":
            stack.append(class_starts.get(index))
        elif character == "}" and stack:
            stack.pop()
        owners[index] = next((owner for owner in reversed(stack) if owner), None)
    properties = set()
    for match in OBSERVABLE_PROPERTY_PATTERN.finditer(source):
        owner = owners.get(match.start())
        assert owner, "ObservableProperty outside a recognized class"
        properties.add((owner, _pascal_case(match[1])))
    collections = {}
    for match in re.finditer(
        r"\bpublic\s+ObservableCollection<(\w+)>\s+(\w+)\s*\{", source
    ):
        owner = owners.get(match.start())
        if owner:
            collections[(owner, match[2])] = match[1]
    return properties, collections


def _binding_options(value: str) -> dict[str, str] | None:
    """Split Binding markup only at unquoted, outer commas."""
    match = re.fullmatch(r"\{Binding(?:\s+(.*))?\}", value.strip(), re.DOTALL)
    if match is None:
        return None
    parts, current = [], []
    depth = 0
    quote = None
    for character in match[1] or "":
        if quote:
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(character)
    parts.append("".join(current).strip())
    options = {}
    for index, part in enumerate(parts):
        if "=" in part:
            key, value = part.split("=", 1)
            options[key.strip()] = value.strip().strip("\"'")
        elif index == 0:
            options["Path"] = part.strip("\"'")
    return options


def _binding_keys(
    xaml: str, root_owner: str, collections: dict[tuple[str, str], str] | None = None
) -> set[tuple[str, str]]:
    """Read exact first path segments in their proven DataContext scope.

    Unknown item/foreign contexts deliberately cannot satisfy root VM coverage.
    Resource templates only gain an owner through an explicit ViewModels type.
    """
    collections = collections or {}
    namespaces = dict(pair for _, pair in ET.iterparse(io.StringIO(xaml), events=("start-ns",)))
    root = ET.fromstring(xaml)  # default parser discards XML comments
    keys: set[tuple[str, str]] = set()
    root_tag = root.tag.rsplit("}", 1)[-1]

    def record(options: dict[str, str] | None, owner: str | None) -> None:
        if options is None:
            return
        path = options.get("Path", "")
        if "Source" in options or "ElementName" in options:
            return
        if "RelativeSource" in options:
            relative = options["RelativeSource"]
            ancestor = re.search(r"AncestorType\s*=\s*(?:\{x:Type\s+)?(\w+)\s*\}?", relative)
            if not ancestor or ancestor[1] != root_tag or not path.startswith("DataContext."):
                return
            owner, path = root_owner, path.removeprefix("DataContext.")
        match = re.match(r"^([A-Za-z_]\w*)(?=$|\.|\[|/)", path)
        if owner and match:
            keys.add((owner, match[1]))

    def walk(element: ET.Element, owner: str | None, item_owner: str | None = None) -> None:
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"DataTemplate", "HierarchicalDataTemplate"}:
            type_match = re.fullmatch(r"\{x:Type\s+(\w+):(\w+)\}", element.get("DataType", ""))
            owner = item_owner
            if type_match:
                owner = type_match[2] if namespaces.get(type_match[1]) == "clr-namespace:PBStudio.UI.ViewModels" else None
            item_owner = None
        elif tag == "ControlTemplate" or tag.endswith(".Resources"):
            owner = None
        elif tag.endswith((".ItemContainerStyle", ".Columns")) or tag == "GridView":
            owner = item_owner
        explicit_context = "DataContext" in element.attrib or any(
            child.tag.rsplit("}", 1)[-1].endswith(".DataContext") for child in element
        )
        if explicit_context:
            # The source binding that sets DataContext still belongs to the parent.
            record(_binding_options(element.get("DataContext", "")), owner)
            owner = None
        for attribute, value in element.attrib.items():
            if attribute.startswith("{") or attribute == "DataContext":
                continue  # ignore design-time attributes
            record(_binding_options(value), owner)
        if tag == "Binding":
            options = dict(element.attrib)
            for child in element:
                child_tag = child.tag.rsplit("}", 1)[-1]
                if child_tag.startswith("Binding."):
                    # Explicit source/property elements must never look like an
                    # implicit binding to the current ViewModel.
                    options[child_tag.removeprefix("Binding.")] = ""
            record(options, owner)
        items = _binding_options(element.get("ItemsSource", ""))
        if items is not None:
            item_owner = collections.get((owner, items.get("Path", ""))) if owner else None
        for child in element:
            walk(child, owner, item_owner)

    walk(root, root_owner)
    return keys


@pytest.fixture(scope="module")
def members() -> tuple[set[tuple[str, str]], dict[tuple[str, str], str]]:
    properties, collections = set(), {}
    for path in sorted(VIEWMODEL_DIR.glob("*.cs")):
        found, items = _class_members(path.read_text(encoding="utf-8-sig"))
        properties.update(found)
        collections.update(items)
    assert properties, "Keine ObservableProperties gefunden — Parser oder Pfad kaputt."
    return properties, collections


@pytest.fixture(scope="module")
def bindings(members) -> set[tuple[str, str]]:
    result = set()
    for relative, owner in VIEW_CONTEXTS.items():
        result.update(_binding_keys((UI_ROOT / relative).read_text(encoding="utf-8-sig"), owner, members[1]))
    return result


def test_view_context_map_covers_every_view() -> None:
    actual = {path.relative_to(UI_ROOT).as_posix() for path in (UI_ROOT / "Views").glob("*.xaml")}
    assert actual | {"MainWindow.xaml"} == set(VIEW_CONTEXTS)


def test_every_observable_property_is_bound_or_documented(members, bindings) -> None:
    undocumented = sorted(f"{owner}.{prop}" for owner, prop in members[0] - bindings
                          if f"{owner}.{prop}" not in INTENTIONALLY_UNBOUND)
    assert not undocumented, (
        "ObservableProperties ohne Binding im passenden DataContext oder dokumentierte Ausnahme:\n  "
        + "\n  ".join(undocumented)
    )


def test_exception_list_has_no_stale_entries(members, bindings) -> None:
    existing = {f"{owner}.{prop}" for owner, prop in members[0]}
    bound = {f"{owner}.{prop}" for owner, prop in bindings}
    stale = sorted(key for key in INTENTIONALLY_UNBOUND if key not in existing or key in bound)
    assert not stale, "Veraltete INTENTIONALLY_UNBOUND-Eintraege: " + ", ".join(stale)


def test_progress_indicators_are_bound(bindings) -> None:
    required = {
        ("AudioLibraryViewModel", "IsDeleting"),
        ("VideoLibraryViewModel", "IsDeleting"),
        ("VideoLibraryViewModel", "IsLoadingClips"),
        ("SettingsViewModel", "IsCleaningGpu"),
        ("BrainViewModel", "IsLoading"),
        ("DirectorViewModel", "CurrentStep"),
        ("ModelManagerViewModel", "IsLoading"),
        ("ProjectOverviewViewModel", "IsBusy"),
        ("TimelineViewModel", "IsLoading"),
        ("TimelineViewModel", "IsLoadingWaveform"),
        ("VramTelemetryViewModel", "IsLoading"),
    }
    assert required <= bindings, f"Fehlende Fortschrittsanzeigen: {required - bindings}"


def _parser_xaml(body: str) -> str:
    return ('<UserControl xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" '
            'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
            'xmlns:vm="clr-namespace:PBStudio.UI.ViewModels">' + body + '</UserControl>')


@pytest.mark.parametrize("expression", ["{Binding Status}", "{Binding Path=Status}",
    "{Binding Mode=OneWay, Path='Status'}", "{Binding Status.Length}"])
def test_parser_exact_paths_regression(expression: str) -> None:
    assert _binding_keys(_parser_xaml(f'<TextBlock Text="{expression}"/>'), "A") == {("A", "Status")}


def test_parser_prefix_comments_and_foreign_view_regression() -> None:
    a = _binding_keys(_parser_xaml('<!-- <TextBlock Text="{Binding Status}"/> -->'
                                  '<TextBlock Text="{Binding StatusText}"/>'), "A")
    b = _binding_keys(_parser_xaml('<TextBlock Text="{Binding Status}"/>'), "B")
    assert ("A", "Status") not in a | b
    assert a | b == {("A", "StatusText"), ("B", "Status")}


def test_parser_template_contexts_regression() -> None:
    xaml = _parser_xaml('''<StackPanel>
      <DataTemplate><TextBlock Text="{Binding Unknown}"/></DataTemplate>
      <DataTemplate DataType="{x:Type vm:Card}"><TextBlock Text="{Binding Status}"/></DataTemplate>
      <ItemsControl ItemsSource="{Binding Cards}"><ItemsControl.ItemTemplate>
        <DataTemplate><TextBlock Text="{Binding Count}"/></DataTemplate>
      </ItemsControl.ItemTemplate></ItemsControl></StackPanel>''')
    assert _binding_keys(xaml, "A", {("A", "Cards"): "Card"}) == {
        ("A", "Cards"), ("Card", "Status"), ("Card", "Count")}


def test_parser_foreign_sources_and_explicit_context_regression() -> None:
    xaml = _parser_xaml('''<StackPanel>
      <TextBlock Text="{Binding Status, ElementName=Other}"/>
      <TextBlock Text="{Binding Status, Source={StaticResource Other}}"/>
      <TextBlock Text="{Binding Status, RelativeSource={RelativeSource Self}}"/>
      <Grid DataContext="{Binding Other}"><TextBlock Text="{Binding Status}"/></Grid>
      <Grid><Grid.DataContext><vm:Other/></Grid.DataContext><TextBlock Text="{Binding Status}"/></Grid>
      <TextBlock><TextBlock.Text><Binding Path="Title"/></TextBlock.Text></TextBlock>
      <TextBlock><TextBlock.Text><Binding Path="Status"><Binding.Source><vm:Other/></Binding.Source></Binding></TextBlock.Text></TextBlock>
    </StackPanel>''')
    assert _binding_keys(xaml, "A") == {("A", "Other"), ("A", "Title")}


def test_parser_template_ancestor_context_regression() -> None:
    xaml = _parser_xaml('''<DataTemplate><TextBlock><TextBlock.Text>
      <Binding Path="DataContext.Status" RelativeSource="{RelativeSource AncestorType=UserControl}"/>
    </TextBlock.Text></TextBlock></DataTemplate>''')
    assert _binding_keys(xaml, "A") == {("A", "Status")}


def test_parser_implicit_item_contexts_regression() -> None:
    xaml = _parser_xaml('''<StackPanel>
      <DataGrid ItemsSource="{Binding Cards}"><DataGrid.Columns>
        <DataGridTextColumn Binding="{Binding Status}"/>
      </DataGrid.Columns></DataGrid>
      <ListView ItemsSource="{Binding Cards}"><ListView.View><GridView>
        <GridViewColumn DisplayMemberBinding="{Binding Name}"/>
      </GridView></ListView.View><ListView.ItemContainerStyle><Style>
        <Setter Property="IsSelected" Value="{Binding Selected}"/>
      </Style></ListView.ItemContainerStyle></ListView>
    </StackPanel>''')
    assert _binding_keys(xaml, "A", {("A", "Cards"): "Card"}) == {
        ("A", "Cards"), ("Card", "Status"), ("Card", "Name"), ("Card", "Selected")}


def test_parser_declaring_class_regression() -> None:
    source = '''class Root {
      // [ObservableProperty] private int _fake;
      string text = "class Fake {";
      [ObservableProperty] private int _first;
      public ObservableCollection<Card> Cards { get; } = new();
      class Nested { [ObservableProperty] private int _child; }
      [ObservableProperty] private int _last;
    }
    class Card { [ObservableProperty] private int _count; }'''
    assert _class_members(source) == ({("Root", "First"), ("Root", "Last"),
        ("Nested", "Child"), ("Card", "Count")}, {("Root", "Cards"): "Card"})
