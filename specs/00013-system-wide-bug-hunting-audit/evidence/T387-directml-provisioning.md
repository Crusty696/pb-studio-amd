# T387 DirectML Provisioning

Date: 2026-07-31
Result: PASS

## Release bundle

- Local artifact: `release-assets/pb-studio-directml-assets-2026.07.31.zip`
- Size: `3,219,585,582` bytes
- SHA-256: `397f4b332a265b71ac555f7209fdb4a140bb2efc5168f51297cff5ea93e4b96d`
- Manifest: `config/directml-asset-bundle.json`
- Payload: 12 model/runtime files and 4 immutable license records.
- `release-assets/` is intentionally ignored; a release or clean-checkout run must supply the exact manifest-bound archive.

## Immutable provenance

- RAFT: torchvision commit `61943691d3390bd3148a7003b4a501f0e2b7ac6e`; 106/106 ONNX initializers exactly matched the official `RAFT_Small_Weights.C_T_V2` state dict.
- SigLIP: `google/siglip-so400m-patch14-384@9fdffc58afc957d1a03a25b10dba0329ab15c2a3`; 448/448 vision initializers matched exactly, including 164 deterministic matrix transposes.
- CLAP: `ConceptualMachines/magda-sample-tagger@f24970352f239768aaad48cc8734fb298441a763` with processor revision `laion/clap-htsat-unfused@8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a`.
- Moondream: `Heliosoph/moondream2-onnx@e48d8acc253b09d8f201206aa126388742298452`.
- The bundle contains exact BSD-3-Clause and Apache-2.0 texts plus the CLAP derived-model license chain.

## Provisioning contract

- `scripts/provision_directml_assets.ps1` fails closed on an unapproved/incomplete manifest.
- Archive names and install targets are allowlisted and constrained below `models/`.
- Archive and every entry are size/SHA-256 checked before promotion.
- Extraction rejects undeclared, duplicate, traversal and symlink entries.
- Promotion uses same-volume staging, atomic replacement and rollback.
- `setup_pb_studio.ps1` phase B.10 invokes this contract and cannot bypass mandatory assets.

## Verification

- Independent ZIP pass: 16/16 declared entries, exact order, sizes and SHA-256 values.
- Provisioner executed against the actual archive: PASS.
- Installed payload and four license targets: PASS.
- Manifest JSON and PowerShell AST: PASS.
- `git diff --check`: PASS.
- Functional DirectML hardware validation remains intentionally assigned to T411.
