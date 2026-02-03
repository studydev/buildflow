#!/usr/bin/env python3
"""Test YouTube transcript fetching."""

import sys

sys.path.insert(0, "/Users/hyounsookim/Desktop/Azure/buildflow/backend")

from youtube_transcript_api import YouTubeTranscriptApi

video_id = "OhI005_aJkA"
print(f"Testing transcript for video: {video_id}")

try:
    # New API in v1.2+: create instance first
    api = YouTubeTranscriptApi()

    # List available transcripts
    transcript_list = api.list(video_id)
    print("Available transcripts:")
    for t in transcript_list:
        print(f"  - {t.language} ({t.language_code}) - Generated: {t.is_generated}")

    # Try to get English first, then any available
    transcript = None
    try:
        transcript = transcript_list.find_transcript(["en"]).fetch()
        print(f"Got English transcript with {len(transcript)} segments")
    except Exception as e1:
        print(f"No English transcript: {e1}")
        try:
            transcript = transcript_list.find_transcript(["ko"]).fetch()
            print(f"Got Korean transcript with {len(transcript)} segments")
        except Exception as e2:
            print(f"No Korean transcript: {e2}")
            try:
                transcript = transcript_list.find_generated_transcript(["en", "ko"]).fetch()
                print(f"Got generated transcript with {len(transcript)} segments")
            except Exception as e3:
                print(f"No generated transcript: {e3}")

    if transcript:
        # Show first 3 segments (new API: use attributes instead of dict)
        print("\nFirst 3 segments:")
        for seg in transcript[:3]:
            print(f"  [{seg.start:.1f}s] {seg.text[:100]}")

        # Full text preview
        full_text = " ".join([s.text for s in transcript])
        print(f"\nTotal text length: {len(full_text)} chars")
        print(f"Preview: {full_text[:500]}...")
    else:
        print("No transcript available")

except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
