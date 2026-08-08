# Inert project fragment

`crafted-timeline-fragment.json` documents the untrusted `audio_path` shape used
by this finding. It is inert data and uses the reserved `example.invalid`
domain.

Do not open this fragment in PB Studio, replace the host, start a listener, or
exercise media playback outside an explicitly authorized isolated lab. No PoC
was executed during this review.

For later T332+ validation, copy the structure into a disposable project only
after replacing the URI with an approved loopback-only test endpoint. Observe
dialog-open, Play, and Restart separately. A fixed build must reject the value
before it reaches `MediaElement.Source` and must generate no request.
