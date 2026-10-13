# Workflowformat — Welle-A-Grenze

Welle A entdeckt ausschließlich Server-/Node-/Modellinformationen. Sie registriert, aktiviert und versendet keine Workflows. APIgraph, immutable Bundlerevision, typisierte Parameter-/Outputadapter und Aktivierungs-CAS gehören zum noch offenen T005.

Node-Schemahash und benannte Modellrolle sind Discoverydaten; sie beweisen weder Ausführbarkeit noch Modellinhalt. Ein gelisteter Name ohne geprüfte Inhaltsidentität bleibt unknown. Sourceprofil und bestätigtes Laufzeitprofil müssen getrennt bleiben. Vollständiger Zielvertrag: specs/00037-comfyui-control-center/plan.md §§P/Q und communication-contract.md.

## Implementierter Vertrag Welle B

JSONbundle enthält manifest und api_prompt; UIgraphen werden abgewiesen. Vollständige Pflichtfelder und zulässige Typen definiert workflow_schemas.py; ausführbares minimales Vertragsfixture in Tests/test_comfyui_workflow_bundle.py, kein qualifizierter Pilotworkflow. node_requirements enthält raw_schema mit zur Discovery passendem schema_sha256; Parameter dürfen Nodegrenzen nicht erweitern. Modellnamen müssen im beobachteten Rolleninventar existieren; ein angegebener SHA benötigt separat verifizierte Modellidentität.

Parameter nur über deklarierte Bindings. Pflichtoutputs binden Node/Slot/Ordinal/Feld/Familie; Adapter comfy.files.v1 statisch. Enum-/dynamische Schemas und literale Listen derzeit unsupported und abgewiesen. Keine Codeimporte aus Workflowmetadaten. Eine Aktivierung qualifiziert keine Ausführung; declared_only bleibt unqualified.
