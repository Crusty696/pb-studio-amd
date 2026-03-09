"""
CLAP Audio Analysis Demo

Demonstrates zero-shot audio classification with the CLAP model.

Requirements:
- CLAP ONNX model files in models/ directory
- Audio files for analysis

Usage:
    python examples/clap_demo.py path/to/audio.mp3
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from pb_studio.ai import CLAPAnalyzer


def demo_mood_analysis(audio_path: str):
    """Demo: Mood/emotion detection"""
    print("\n=== Mood Analysis ===")

    analyzer = CLAPAnalyzer()

    if not analyzer.is_ready:
        print("ERROR: CLAP model not initialized")
        print("Please download ONNX models to models/ directory")
        return

    print(f"Active Provider: {analyzer.active_provider}")
    print(f"Analyzing: {audio_path}")

    # Get mood tags
    moods = analyzer.get_mood_tags(audio_path, top_k=5)

    print("\nTop 5 Moods:")
    for i, mood in enumerate(moods, 1):
        print(f"  {i}. {mood}")


def demo_comprehensive_analysis(audio_path: str):
    """Demo: Full audio analysis"""
    print("\n=== Comprehensive Audio Analysis ===")

    analyzer = CLAPAnalyzer()

    if not analyzer.is_ready:
        print("ERROR: CLAP model not initialized")
        return

    print(f"Analyzing: {audio_path}")

    # Get all analysis results
    results = analyzer.analyze_audio_comprehensive(audio_path)

    print("\nMoods:")
    for mood in results["moods"]:
        print(f"  - {mood}")

    print("\nInstruments:")
    for instrument in results["instruments"]:
        print(f"  - {instrument}")

    print("\nGenres:")
    for genre in results["genres"]:
        print(f"  - {genre}")

    if results["embedding"] is not None:
        print(f"\nEmbedding Shape: {results['embedding'].shape}")
        print(f"Embedding Norm: {results['embedding'].sum():.4f}")


def demo_custom_classification(audio_path: str):
    """Demo: Custom label classification"""
    print("\n=== Custom Classification ===")

    analyzer = CLAPAnalyzer()

    if not analyzer.is_ready:
        print("ERROR: CLAP model not initialized")
        return

    # Define custom labels
    custom_labels = [
        "workout music",
        "meditation music",
        "background music for studying",
        "party music",
        "relaxation music",
        "focus music",
        "sleep music"
    ]

    print(f"Analyzing: {audio_path}")
    print(f"Custom Labels: {', '.join(custom_labels)}")

    # Classify
    results = analyzer.classify_audio(audio_path, custom_labels, top_k=3)

    print("\nTop 3 Matches:")
    for label, score in results:
        print(f"  {label}: {score:.4f}")


def demo_similarity(audio_path1: str, audio_path2: str):
    """Demo: Audio similarity comparison"""
    print("\n=== Audio Similarity ===")

    analyzer = CLAPAnalyzer()

    if not analyzer.is_ready:
        print("ERROR: CLAP model not initialized")
        return

    print(f"Comparing:")
    print(f"  File 1: {audio_path1}")
    print(f"  File 2: {audio_path2}")

    # Compute similarity
    similarity = analyzer.compute_similarity(audio_path1, audio_path2)

    print(f"\nSimilarity Score: {similarity:.4f}")

    if similarity > 0.9:
        print("Interpretation: Very similar")
    elif similarity > 0.7:
        print("Interpretation: Similar")
    elif similarity > 0.5:
        print("Interpretation: Somewhat similar")
    else:
        print("Interpretation: Different")


def main():
    """Main demo runner"""
    if len(sys.argv) < 2:
        print("Usage: python examples/clap_demo.py <audio_path> [audio_path2]")
        print("\nExamples:")
        print("  python examples/clap_demo.py music/song.mp3")
        print("  python examples/clap_demo.py music/song1.mp3 music/song2.mp3")
        sys.exit(1)

    audio_path = sys.argv[1]

    # Verify audio file exists
    if not Path(audio_path).exists():
        print(f"ERROR: Audio file not found: {audio_path}")
        sys.exit(1)

    print("=" * 60)
    print("CLAP Audio Analysis Demo")
    print("=" * 60)

    # Run demos
    demo_mood_analysis(audio_path)
    demo_comprehensive_analysis(audio_path)
    demo_custom_classification(audio_path)

    # If second audio file provided, compare similarity
    if len(sys.argv) >= 3:
        audio_path2 = sys.argv[2]
        if Path(audio_path2).exists():
            demo_similarity(audio_path, audio_path2)
        else:
            print(f"\nWARNING: Second audio file not found: {audio_path2}")

    print("\n" + "=" * 60)
    print("Demo Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
