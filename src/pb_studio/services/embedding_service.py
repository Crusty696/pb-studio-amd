"""Background-Queue für Audio/Video-Embeddings (Plan Phase 2).

Async worker, SSE progress via publish_event.
Hash-Cache via EmbeddingCache (cross-project).
Repository per project via EmbeddingRepository.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EmbedJob:
    job_id: str
    media_type: str        # "audio" | "video"
    media_path: str
    media_id: int
    media_hash: str
    extra: dict


PublishFn = Callable[[str, dict], Awaitable[None]]


class EmbeddingService:
    """Single global queue for embedding jobs."""

    def __init__(
        self,
        *,
        repository,
        cache,
        publish: Optional[PublishFn] = None,
        prefer_directml: bool = True,
    ):
        self.repository = repository
        self.cache = cache
        self.publish = publish
        self.prefer_directml = prefer_directml
        self._queue: asyncio.Queue[EmbedJob] = asyncio.Queue()
        self._worker: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._running = False
        if self._worker:
            await self._queue.put(None)  # type: ignore[arg-type]
            await self._worker
            self._worker = None

    async def enqueue_audio(
        self, *, job_id: str, media_path: str, media_id: int,
        media_hash: str, section_segments: Optional[list[tuple[float, float]]] = None,
    ) -> None:
        await self._queue.put(EmbedJob(
            job_id=job_id, media_type="audio", media_path=media_path,
            media_id=media_id, media_hash=media_hash,
            extra={"section_segments": section_segments or []},
        ))

    async def enqueue_video(
        self, *, job_id: str, media_path: str, media_id: int,
        media_hash: str, scenes: list[tuple[float, float]],
    ) -> None:
        await self._queue.put(EmbedJob(
            job_id=job_id, media_type="video", media_path=media_path,
            media_id=media_id, media_hash=media_hash,
            extra={"scenes": scenes},
        ))

    async def _run(self) -> None:
        while self._running:
            try:
                job = await self._queue.get()
            except asyncio.CancelledError:
                return
            if job is None:
                return
            try:
                await self._handle_job(job)
            except Exception as e:
                logger.exception("EmbedJob failed: %s", e)
                await self._notify(job, status="error", message=str(e), percent=100)

    async def _handle_job(self, job: EmbedJob) -> None:
        await self._notify(job, status="running", message="started", percent=0)

        if job.media_type == "audio":
            await self._handle_audio(job)
        elif job.media_type == "video":
            await self._handle_video(job)
        else:
            raise ValueError(f"unknown media_type: {job.media_type}")

        await self._notify(job, status="ok", message="done", percent=100)

    async def _handle_audio(self, job: EmbedJob) -> None:
        from pb_studio.audio.audio_embedder import (
            CURRENT_MODEL_NAME,
            CURRENT_MODEL_VERSION,
            get_audio_embedder,
        )

        cached = self.cache.lookup(
            job.media_hash, CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION
        )
        if cached is not None:
            emb = self.cache.load_array(cached)
            await asyncio.to_thread(
                self.repository.add_audio_unit,
                parent_id=None, level="mix",
                media_id=job.media_id, media_hash=job.media_hash,
                start_time=0.0, end_time=0.0,
                embedding=emb,
                metadata={"source": "cache"},
            )
            await self._notify(job, status="running",
                               message="cache hit", percent=80)
            return

        embedder = get_audio_embedder(prefer_directml=self.prefer_directml)
        result = await asyncio.to_thread(
            embedder.embed_audio,
            job.media_path,
            section_segments=job.extra.get("section_segments") or None,
        )

        await asyncio.to_thread(
            self.cache.store,
            media_hash=job.media_hash,
            media_type="audio",
            embedding=result.mix_embedding,
            model_name=CURRENT_MODEL_NAME,
            model_version=CURRENT_MODEL_VERSION,
        )

        mix_id = await asyncio.to_thread(
            self.repository.add_audio_unit,
            parent_id=None, level="mix",
            media_id=job.media_id, media_hash=job.media_hash,
            start_time=0.0,
            end_time=float(len(result.window_embeddings)) * 5.0,
            embedding=result.mix_embedding,
        )
        for emb, sec in zip(result.section_embeddings,
                            job.extra.get("section_segments") or []):
            await asyncio.to_thread(
                self.repository.add_audio_unit,
                parent_id=mix_id, level="section",
                media_id=job.media_id, media_hash=job.media_hash,
                start_time=float(sec[0]), end_time=float(sec[1]),
                embedding=emb,
            )
        for i, (emb, t) in enumerate(zip(
            result.window_embeddings, result.window_starts
        )):
            await asyncio.to_thread(
                self.repository.add_audio_unit,
                parent_id=mix_id, level="window",
                media_id=job.media_id, media_hash=job.media_hash,
                start_time=float(t), end_time=float(t) + 10.0,
                embedding=emb,
            )

    async def _handle_video(self, job: EmbedJob) -> None:
        from pb_studio.video.video_embedder import (
            CURRENT_MODEL_NAME,
            CURRENT_MODEL_VERSION,
            get_video_embedder,
        )

        cached = self.cache.lookup(
            job.media_hash, CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION
        )
        if cached is not None:
            emb = self.cache.load_array(cached)
            await asyncio.to_thread(
                self.repository.add_video_unit,
                parent_id=None, level="clip",
                media_id=job.media_id, media_hash=job.media_hash,
                start_time=0.0, end_time=0.0,
                embedding=emb, metadata={"source": "cache"},
            )
            await self._notify(job, status="running",
                               message="cache hit", percent=80)
            return

        embedder = get_video_embedder(prefer_directml=self.prefer_directml)
        scenes: list[tuple[float, float]] = list(job.extra.get("scenes") or [])
        result = await asyncio.to_thread(
            embedder.embed_scenes, job.media_path, scenes=scenes,
        )

        await asyncio.to_thread(
            self.cache.store,
            media_hash=job.media_hash, media_type="video",
            embedding=result.clip_embedding,
            model_name=CURRENT_MODEL_NAME,
            model_version=CURRENT_MODEL_VERSION,
        )

        clip_id = await asyncio.to_thread(
            self.repository.add_video_unit,
            parent_id=None, level="clip",
            media_id=job.media_id, media_hash=job.media_hash,
            start_time=0.0,
            end_time=float(scenes[-1][1]) if scenes else 0.0,
            embedding=result.clip_embedding,
        )
        
        # Bulk-Insert für alle Szenen-Einheiten
        scenes_data = [
            {
                "parent_id": clip_id,
                "level": "scene",
                "media_id": job.media_id,
                "media_hash": job.media_hash,
                "start_time": float(s),
                "end_time": float(e),
                "embedding": emb,
            }
            for (s, e), emb in zip(result.scene_times, result.scene_embeddings)
        ]
        
        if scenes_data:
            await asyncio.to_thread(
                self.repository.add_video_units_bulk,
                scenes_data
            )

    async def _notify(
        self, job: EmbedJob, *, status: str, message: str, percent: int,
    ) -> None:
        if not self.publish:
            return
        await self.publish("embedding_progress", {
            "job_id": job.job_id, "media_type": job.media_type,
            "media_id": job.media_id, "status": status,
            "message": message, "percent": percent,
        })
