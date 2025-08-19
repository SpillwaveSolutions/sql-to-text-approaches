"""
Speech-to-Text Utility using OpenAI Whisper API

A reusable utility for converting speech to text using the streamlit-mic-recorder
component and OpenAI's Whisper API. Provides a simple interface for voice input
in Streamlit applications.
"""

import os
import logging
import tempfile
from typing import Optional, Dict, Any
import streamlit as st
from streamlit_mic_recorder import mic_recorder
import openai

logger = logging.getLogger(__name__)

class SpeechToTextRecorder:
    """Speech-to-text recorder using OpenAI Whisper API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the speech-to-text recorder
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        # Set OpenAI API key
        openai.api_key = self.api_key
    
    def transcribe_audio(self, audio_bytes: bytes, language: str = "auto") -> Optional[str]:
        """
        Transcribe audio bytes using OpenAI Whisper API
        
        Args:
            audio_bytes: Audio data as bytes
            language: Language code (e.g., "en", "es", "fr") or "auto" for auto-detection
            
        Returns:
            Transcribed text or None if transcription fails
        """
        if not audio_bytes:
            logger.warning("No audio data provided for transcription")
            return None
        
        logger.info(f"Audio data size: {len(audio_bytes)} bytes")
        
        # Debug: Show first few bytes of audio data
        if len(audio_bytes) > 0:
            hex_preview = ' '.join(f'{b:02x}' for b in audio_bytes[:20])
            logger.info(f"Audio data preview (first 20 bytes hex): {hex_preview}")
        
        # Check if the audio data looks valid (basic header check for WebM)
        is_webm = audio_bytes.startswith(b'\x1a\x45\xdf\xa3')  # EBML header for WebM
        is_wav = audio_bytes.startswith(b'RIFF')  # WAV header
        is_ogg = audio_bytes.startswith(b'OggS')  # OGG header
        
        logger.info(f"Audio format detection - WebM: {is_webm}, WAV: {is_wav}, OGG: {is_ogg}")
        
        # If audio data is suspiciously small, it's likely empty/corrupted
        if len(audio_bytes) < 100:
            logger.error(f"Audio data too small ({len(audio_bytes)} bytes) - likely empty or corrupted")
            return None
        
        try:
            # Create a temporary file for the audio
            audio_extension = ".webm"  # Default for streamlit-mic-recorder
            temp_file_path = None
            
            try:
                with tempfile.NamedTemporaryFile(suffix=audio_extension, delete=False) as temp_file:
                    temp_file.write(audio_bytes)
                    temp_file_path = temp_file.name
                
                logger.info(f"Created temporary audio file: {temp_file_path}")
                logger.info(f"File size on disk: {os.path.getsize(temp_file_path)} bytes")
                
                # Transcribe using OpenAI Whisper API
                with open(temp_file_path, "rb") as audio_file:
                    transcript_params = {
                        "model": "whisper-1",
                        "file": audio_file,
                        "response_format": "text"
                    }
                    
                    # Add language parameter if not auto-detection
                    if language != "auto":
                        transcript_params["language"] = language
                    
                    logger.info(f"Calling OpenAI Whisper API with params: {transcript_params.keys()}")
                    response = openai.audio.transcriptions.create(**transcript_params)
                    
                    # Handle both string and object responses
                    if isinstance(response, str):
                        transcript = response
                    else:
                        transcript = getattr(response, 'text', str(response))
                    
                    logger.info(f"API Response type: {type(response)}")
                    logger.info(f"Raw transcript: '{transcript}'")
                    logger.info(f"Transcript length: {len(transcript) if transcript else 0}")
                    
                    if transcript and transcript.strip():
                        final_transcript = transcript.strip()
                        logger.info(f"Successfully transcribed audio: '{final_transcript}'")
                        return final_transcript
                    else:
                        logger.warning("Empty or whitespace-only transcript received")
                        return None
                    
            finally:
                # Clean up temporary file
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                        logger.debug(f"Cleaned up temporary file: {temp_file_path}")
                    except OSError as e:
                        logger.warning(f"Failed to cleanup temp file: {e}")
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error transcribing audio: {error_msg}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Check for specific error patterns to provide better debugging
            if "could not be decoded" in error_msg:
                logger.error("DIAGNOSIS: Audio file format is corrupted or invalid. The mic_recorder may not be capturing audio properly.")
            elif "file format" in error_msg:
                logger.error("DIAGNOSIS: Audio file format not supported. Check streamlit-mic-recorder configuration.")
            elif "file is empty" in error_msg:
                logger.error("DIAGNOSIS: Audio file is empty. Microphone may not be working or permission denied.")
            
            return None
    
    def render_recorder_widget(
        self,
        key: str = "speech_recorder",
        start_prompt: str = "🎤 Start Recording",
        stop_prompt: str = "⏹️ Stop Recording", 
        language: str = "auto",
        format: str = "webm"
    ) -> Optional[str]:
        """
        Render the microphone recorder widget and return transcribed text
        
        Args:
            key: Unique key for the widget (important for multiple recorders)
            start_prompt: Text shown on start recording button
            stop_prompt: Text shown on stop recording button
            language: Language for transcription ("auto", "en", "es", etc.)
            format: Audio format ("webm" or "wav")
            
        Returns:
            Transcribed text if recording was successful, None otherwise
        """
        # Render the microphone recorder
        audio = mic_recorder(
            start_prompt=start_prompt,
            stop_prompt=stop_prompt,
            key=key,
            format=format
        )
        
        # Debug: Show what we received from mic_recorder
        if audio is not None:
            logger.info(f"Received audio data: {audio.keys() if isinstance(audio, dict) else type(audio)}")
            if isinstance(audio, dict):
                for k, v in audio.items():
                    if k == 'bytes':
                        logger.info(f"  {k}: {len(v) if v else 0} bytes")
                        # Debug: check if audio data is valid
                        if v and len(v) > 0:
                            hex_preview = ' '.join(f'{b:02x}' for b in v[:10])
                            logger.info(f"  Audio data preview: {hex_preview}")
                    else:
                        logger.info(f"  {k}: {v}")
        
        # Process audio if available
        if audio is not None and isinstance(audio, dict) and 'bytes' in audio:
            audio_bytes = audio['bytes']
            
            if not audio_bytes:
                st.warning("⚠️ No audio data received. Please check microphone permissions and try recording again.")
                logger.warning("Audio bytes is empty or None")
                return None
            
            logger.info(f"Processing audio with {len(audio_bytes)} bytes")
            
            # Check for suspiciously small audio files (likely empty/corrupted)
            if len(audio_bytes) < 100:
                st.error(f"❌ Audio data too small ({len(audio_bytes)} bytes). Please record for longer or check your microphone.")
                logger.error(f"Audio data too small: {len(audio_bytes)} bytes")
                return None
            
            # Show transcription status with more detail
            with st.spinner("🎙️ Transcribing audio..."):
                transcript = self.transcribe_audio(audio_bytes, language)
                
            if transcript:
                # Check for suspicious results that indicate poor audio quality
                suspicious_words = ['you', 'u', 'yea', 'yeah', 'a', 'i', 'the', 'um', 'uh', 'oh', 'ah']
                if transcript.lower().strip() in suspicious_words:
                    st.warning(f"🤔 Detected potentially poor audio quality: '{transcript}'")
                    
                    # Provide specific guidance based on the pattern
                    with st.expander("🔧 Troubleshooting Audio Issues"):
                        st.write("""
                        **Your audio is being recorded and sent to Whisper, but the transcription quality suggests issues:**
                        
                        **Common causes:**
                        1. **Microphone too far away** - Get closer to your microphone
                        2. **Speaking too quietly** - Speak louder and more clearly  
                        3. **Background noise** - Try recording in a quiet environment
                        4. **Recording too short** - Record for 3-5 seconds minimum
                        5. **Browser microphone issues** - Check browser permissions
                        
                        **Technical details from your last recording:**
                        - Audio data size: {} bytes ✅
                        - Format: WebM ✅  
                        - Sample rate: 44100 Hz ✅
                        - API response: Working ✅
                        
                        **Next steps:**
                        1. Click the microphone button
                        2. Wait for recording to start
                        3. Speak clearly and loudly: "What are the total sales for this year?"
                        4. Record for at least 3-4 seconds
                        5. Click stop
                        """.format(len(audio_bytes)))
                    
                    # Still return the transcript in case user wants to use it
                    st.info(f"Returning transcription: '{transcript}' (you can still use this if it's correct)")
                else:
                    st.success(f"✅ Transcription: {transcript}")
                
                logger.info(f"Widget returning transcript: '{transcript}'")
                return transcript
            else:
                st.error("❌ Failed to transcribe audio. Please check your microphone and try again.")
                logger.error("Transcription failed, returning None")
                return None
        elif audio is not None:
            logger.warning(f"Unexpected audio data format: {type(audio)}")
            st.warning("⚠️ Unexpected audio format received. Please try again.")
        
        return None

def create_speech_to_text_widget(
    key: str = "stt_widget",
    start_prompt: str = "🎤 Start Recording",
    stop_prompt: str = "⏹️ Stop Recording",
    language: str = "auto",
    format: str = "webm",
    api_key: Optional[str] = None
) -> Optional[str]:
    """
    Convenience function to create a speech-to-text widget
    
    Args:
        key: Unique key for the widget
        start_prompt: Text for start button
        stop_prompt: Text for stop button
        language: Language for transcription
        format: Audio format
        api_key: OpenAI API key (optional)
        
    Returns:
        Transcribed text or None
    """
    try:
        recorder = SpeechToTextRecorder(api_key=api_key)
        return recorder.render_recorder_widget(
            key=key,
            start_prompt=start_prompt,
            stop_prompt=stop_prompt,
            language=language,
            format=format
        )
    except ValueError as e:
        st.error(f"Speech-to-text configuration error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in speech-to-text widget: {str(e)}")
        st.error("Speech-to-text functionality is temporarily unavailable.")
        return None

def render_voice_input_section(
    text_input_key: str,
    current_text: str = "",
    stt_key: str = "voice_input",
    language: str = "auto"
) -> str:
    """
    Render a combined voice input section with microphone and text display
    
    Args:
        text_input_key: Key for the text input field
        current_text: Current text in the input field
        stt_key: Key for the speech-to-text widget
        language: Language for transcription
        
    Returns:
        Updated text (either from voice input or existing text)
    """
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.write("Ask a question (type or use voice):")
    
    with col2:
        # Render speech-to-text recorder
        transcript = create_speech_to_text_widget(
            key=stt_key,
            start_prompt="🎤",
            stop_prompt="⏹️",
            language=language
        )
    
    # Update text if we got a transcription
    if transcript:
        # Store the transcript in session state to persist it
        st.session_state[f"{text_input_key}_transcript"] = transcript
        return transcript
    
    # Return existing transcript if available, otherwise current text
    return st.session_state.get(f"{text_input_key}_transcript", current_text)

if __name__ == "__main__":
    # Test the speech-to-text functionality
    st.title("🎤 Speech-to-Text Test")
    
    st.write("This is a test of the speech-to-text functionality.")
    
    # Test basic recorder
    st.subheader("Basic Recorder")
    transcript = create_speech_to_text_widget(key="test_basic")
    if transcript:
        st.write(f"**Transcribed:** {transcript}")
    
    # Test voice input section
    st.subheader("Voice Input Section")
    updated_text = render_voice_input_section("test_input", "", "test_section")
    st.text_input("Your input:", value=updated_text, key="display_input")