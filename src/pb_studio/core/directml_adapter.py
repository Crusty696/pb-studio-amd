"""Central DXGI adapter selection for every DirectML consumer."""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

logger = logging.getLogger(__name__)

_AMD_VENDOR_ID = 0x1002
_DXGI_ADAPTER_FLAG_SOFTWARE = 0x2
_DXGI_ERROR_NOT_FOUND = 0x887A0002
_DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE = 2
_MIN_DISCRETE_VRAM_BYTES = 1024 * 1024 * 1024
_DEFAULT_POLICY = "highest_vram_amd"


class DirectMLAdapterError(RuntimeError):
    """Raised when the AMD DirectML adapter contract cannot be satisfied."""


@dataclass(frozen=True)
class DirectMLAdapter:
    device_id: int
    luid: str
    name: str
    vendor_id: int
    device_id_pci: int
    dedicated_vram_bytes: int
    shared_system_memory_bytes: int
    is_software: bool
    is_discrete: bool
    high_performance_preferred: bool
    selection_policy: str
    selection_reason: str

    @property
    def dedicated_vram_mb(self) -> int:
        return self.dedicated_vram_bytes // (1024 * 1024)

    @property
    def provider_tuple(self) -> tuple[str, dict[str, int]]:
        return ("DmlExecutionProvider", {"device_id": self.device_id})


if sys.platform == "win32":
    _HRESULT = ctypes.c_long
    _UINT = ctypes.c_uint
    _SIZE_T = ctypes.c_size_t

    class _GUID(ctypes.Structure):
        _fields_ = (
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        )

        @classmethod
        def from_string(cls, value: str) -> "_GUID":
            import uuid

            raw = uuid.UUID(value).bytes_le
            return cls.from_buffer_copy(raw)

    class _LUID(ctypes.Structure):
        _fields_ = (("LowPart", ctypes.c_uint32), ("HighPart", ctypes.c_int32))

    class _DXGI_ADAPTER_DESC1(ctypes.Structure):
        _fields_ = (
            ("Description", ctypes.c_wchar * 128),
            ("VendorId", _UINT),
            ("DeviceId", _UINT),
            ("SubSysId", _UINT),
            ("Revision", _UINT),
            ("DedicatedVideoMemory", _SIZE_T),
            ("DedicatedSystemMemory", _SIZE_T),
            ("SharedSystemMemory", _SIZE_T),
            ("AdapterLuid", _LUID),
            ("Flags", _UINT),
        )

    _IID_IDXGI_FACTORY1 = _GUID.from_string(
        "770aae78-f26f-4dba-a829-253c83d1b387"
    )
    _IID_IDXGI_FACTORY6 = _GUID.from_string(
        "c1b6694f-ff09-44a9-b03c-77900a0a1d17"
    )
    _IID_IDXGI_ADAPTER1 = _GUID.from_string(
        "29038f61-3839-4626-91fd-086879011a05"
    )


def _unsigned_hresult(value: int) -> int:
    return value & 0xFFFFFFFF


def _check_hresult(value: int, operation: str) -> None:
    if value < 0:
        raise DirectMLAdapterError(
            f"{operation} failed with HRESULT 0x{_unsigned_hresult(value):08x}"
        )


def _com_method(
    interface: ctypes.c_void_p,
    index: int,
    restype: Any,
    *argtypes: Any,
) -> Any:
    if not interface or not interface.value:
        raise DirectMLAdapterError("DXGI returned a null COM interface")
    vtable = ctypes.cast(
        interface,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
    ).contents
    address = vtable[index]
    prototype = ctypes.WINFUNCTYPE(
        restype,
        ctypes.c_void_p,
        *argtypes,
    )
    return prototype(address)


def _release(interface: ctypes.c_void_p) -> None:
    if interface and interface.value:
        _com_method(interface, 2, ctypes.c_ulong)(interface)


def _query_interface(
    interface: ctypes.c_void_p,
    interface_id: Any,
) -> ctypes.c_void_p | None:
    result = ctypes.c_void_p()
    query = _com_method(
        interface,
        0,
        _HRESULT,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    )
    hr = query(interface, ctypes.byref(interface_id), ctypes.byref(result))
    if hr < 0:
        return None
    return result


def _format_luid(luid: Any) -> str:
    return (
        f"0x{luid.HighPart & 0xFFFFFFFF:08x}_"
        f"0x{luid.LowPart & 0xFFFFFFFF:08x}"
    )


def _get_adapter_desc(adapter: ctypes.c_void_p) -> Any:
    desc = _DXGI_ADAPTER_DESC1()
    get_desc = _com_method(
        adapter,
        10,
        _HRESULT,
        ctypes.POINTER(_DXGI_ADAPTER_DESC1),
    )
    _check_hresult(get_desc(adapter, ctypes.byref(desc)), "IDXGIAdapter1::GetDesc1")
    return desc


def _high_performance_luid(factory1: ctypes.c_void_p) -> str | None:
    factory6 = _query_interface(factory1, _IID_IDXGI_FACTORY6)
    if factory6 is None:
        return None
    adapter = ctypes.c_void_p()
    try:
        enum_preferred = _com_method(
            factory6,
            29,
            _HRESULT,
            _UINT,
            _UINT,
            ctypes.POINTER(_GUID),
            ctypes.POINTER(ctypes.c_void_p),
        )
        hr = enum_preferred(
            factory6,
            0,
            _DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,
            ctypes.byref(_IID_IDXGI_ADAPTER1),
            ctypes.byref(adapter),
        )
        if hr < 0:
            return None
        return _format_luid(_get_adapter_desc(adapter).AdapterLuid)
    finally:
        _release(adapter)
        _release(factory6)


def enumerate_dxgi_adapters() -> tuple[DirectMLAdapter, ...]:
    """Enumerate normal DXGI adapter indices used by DirectML device_id."""

    if sys.platform != "win32":
        raise DirectMLAdapterError("DirectML adapter enumeration requires Windows")

    factory = ctypes.c_void_p()
    create_factory = ctypes.WinDLL("dxgi.dll").CreateDXGIFactory1
    create_factory.argtypes = (
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    )
    create_factory.restype = _HRESULT
    _check_hresult(
        create_factory(ctypes.byref(_IID_IDXGI_FACTORY1), ctypes.byref(factory)),
        "CreateDXGIFactory1",
    )

    adapters: list[DirectMLAdapter] = []
    try:
        preferred_luid = _high_performance_luid(factory)
        enum_adapters = _com_method(
            factory,
            12,
            _HRESULT,
            _UINT,
            ctypes.POINTER(ctypes.c_void_p),
        )
        index = 0
        while True:
            adapter = ctypes.c_void_p()
            hr = enum_adapters(factory, index, ctypes.byref(adapter))
            if _unsigned_hresult(hr) == _DXGI_ERROR_NOT_FOUND:
                break
            _check_hresult(hr, f"IDXGIFactory1::EnumAdapters1({index})")
            try:
                desc = _get_adapter_desc(adapter)
                luid = _format_luid(desc.AdapterLuid)
                dedicated = int(desc.DedicatedVideoMemory)
                adapters.append(
                    DirectMLAdapter(
                        device_id=index,
                        luid=luid,
                        name=desc.Description.rstrip("\x00"),
                        vendor_id=int(desc.VendorId),
                        device_id_pci=int(desc.DeviceId),
                        dedicated_vram_bytes=dedicated,
                        shared_system_memory_bytes=int(desc.SharedSystemMemory),
                        is_software=bool(
                            int(desc.Flags) & _DXGI_ADAPTER_FLAG_SOFTWARE
                        ),
                        is_discrete=dedicated >= _MIN_DISCRETE_VRAM_BYTES,
                        high_performance_preferred=luid == preferred_luid,
                        selection_policy=_DEFAULT_POLICY,
                        selection_reason="enumerated",
                    )
                )
            finally:
                _release(adapter)
            index += 1
    finally:
        _release(factory)

    if not adapters:
        raise DirectMLAdapterError("DXGI returned no adapters")
    return tuple(adapters)


def _validated_device_id(value: Any, source: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DirectMLAdapterError(
            f"{source} must be a non-negative integer DirectML device ID"
        )
    return value


def _with_selection(
    adapter: DirectMLAdapter,
    policy: str,
    reason: str,
) -> DirectMLAdapter:
    return DirectMLAdapter(
        device_id=adapter.device_id,
        luid=adapter.luid,
        name=adapter.name,
        vendor_id=adapter.vendor_id,
        device_id_pci=adapter.device_id_pci,
        dedicated_vram_bytes=adapter.dedicated_vram_bytes,
        shared_system_memory_bytes=adapter.shared_system_memory_bytes,
        is_software=adapter.is_software,
        is_discrete=adapter.is_discrete,
        high_performance_preferred=adapter.high_performance_preferred,
        selection_policy=policy,
        selection_reason=reason,
    )


def select_directml_adapter(
    adapters: Sequence[DirectMLAdapter],
    config: Mapping[str, Any],
) -> DirectMLAdapter:
    """Apply the approved configuration precedence to a DXGI inventory."""

    hardware = config.get("hardware", {})
    ai = config.get("ai", {})
    if not isinstance(hardware, Mapping) or not isinstance(ai, Mapping):
        raise DirectMLAdapterError("hardware and ai configuration must be mappings")

    candidates = [
        item
        for item in adapters
        if not item.is_software and item.vendor_id == _AMD_VENDOR_ID
    ]
    if not candidates:
        raise DirectMLAdapterError(
            "No AMD hardware adapter is available for DirectML"
        )

    configured_source: str | None = None
    configured_id: int | None = None
    if hardware.get("directml_device_id") is not None:
        configured_source = "hardware.directml_device_id"
        configured_id = _validated_device_id(
            hardware["directml_device_id"],
            configured_source,
        )
    elif ai.get("dml_device_id") is not None:
        configured_source = "ai.dml_device_id"
        configured_id = _validated_device_id(
            ai["dml_device_id"],
            configured_source,
        )
        logger.warning(
            "ai.dml_device_id is deprecated; use hardware.directml_device_id"
        )

    if configured_id is not None:
        selected = next(
            (item for item in candidates if item.device_id == configured_id),
            None,
        )
        if selected is None:
            raise DirectMLAdapterError(
                f"{configured_source}={configured_id} does not identify an "
                "AMD hardware adapter"
            )
        discrete_candidates = [item for item in candidates if item.is_discrete]
        if discrete_candidates and not selected.is_discrete:
            raise DirectMLAdapterError(
                f"{configured_source}={configured_id} identifies an integrated "
                "AMD adapter while a discrete AMD adapter is available"
            )
        return _with_selection(
            selected,
            "configured_device_id",
            configured_source,
        )

    policy = hardware.get("directml_adapter_policy", _DEFAULT_POLICY)
    if policy != _DEFAULT_POLICY:
        raise DirectMLAdapterError(
            f"Unsupported hardware.directml_adapter_policy: {policy!r}"
        )

    discrete_candidates = [item for item in candidates if item.is_discrete]
    eligible = discrete_candidates or candidates
    selected = max(
        eligible,
        key=lambda item: (item.dedicated_vram_bytes, -item.device_id),
    )
    return _with_selection(
        selected,
        policy,
        "AMD hardware adapter with highest dedicated VRAM",
    )


_adapter_lock = threading.Lock()
_selected_adapter: DirectMLAdapter | None = None


def get_directml_adapter(
    config: Mapping[str, Any] | None = None,
    *,
    refresh: bool = False,
) -> DirectMLAdapter:
    """Return the process-wide immutable DirectML adapter descriptor."""

    global _selected_adapter
    with _adapter_lock:
        if _selected_adapter is not None and not refresh:
            return _selected_adapter
        if config is None:
            from pb_studio.config_manager import ConfigManager

            manager = ConfigManager()
            config = {
                "hardware": manager.get("hardware", {}),
                "ai": manager.get("ai", {}),
            }
        _selected_adapter = select_directml_adapter(
            enumerate_dxgi_adapters(),
            config,
        )
        logger.info(
            "DirectML adapter selected: index=%d luid=%s name=%s "
            "dedicated_vram_mb=%d policy=%s reason=%s",
            _selected_adapter.device_id,
            _selected_adapter.luid,
            _selected_adapter.name,
            _selected_adapter.dedicated_vram_mb,
            _selected_adapter.selection_policy,
            _selected_adapter.selection_reason,
        )
        return _selected_adapter


def get_directml_provider(
    config: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, int]]:
    return get_directml_adapter(config).provider_tuple


def configure_directml_session_options(session_options: Any) -> Any:
    """Apply the process-wide DirectML-only ONNX Runtime contract."""

    session_options.enable_mem_pattern = False
    session_options.enable_cpu_mem_arena = False
    session_options.add_session_config_entry(
        "session.disable_cpu_ep_fallback",
        "1",
    )
    return session_options


def enforce_directml_session(session: Any) -> Any:
    """Disable ONNX Runtime retries and reject non-DirectML sessions."""

    get_session_options = getattr(session, "get_session_options", None)
    if not callable(get_session_options):
        raise DirectMLAdapterError(
            "ONNX Runtime session does not expose get_session_options()"
        )
    session_options = get_session_options()
    get_config_entry = getattr(
        session_options,
        "get_session_config_entry",
        None,
    )
    if (
        not callable(get_config_entry)
        or get_config_entry("session.disable_cpu_ep_fallback") != "1"
    ):
        raise DirectMLAdapterError(
            "ONNX Runtime CPU EP fallback is not disabled"
        )
    if (
        session_options.enable_mem_pattern
        or session_options.enable_cpu_mem_arena
    ):
        raise DirectMLAdapterError(
            "ONNX Runtime DirectML memory flags are not disabled"
        )

    disable_fallback = getattr(session, "disable_fallback", None)
    if not callable(disable_fallback):
        raise DirectMLAdapterError(
            "ONNX Runtime session does not expose disable_fallback()"
        )
    disable_fallback()

    providers = list(session.get_providers())
    if not providers or providers[0] != "DmlExecutionProvider":
        raise DirectMLAdapterError(
            "ONNX Runtime session does not prioritize DirectML "
            f"(registered providers: {providers})"
        )
    unexpected = set(providers) - {
        "DmlExecutionProvider",
        "CPUExecutionProvider",
    }
    if unexpected:
        raise DirectMLAdapterError(
            "ONNX Runtime session registered an unexpected provider "
            f"(registered providers: {providers})"
        )
    return session
