'use client';

// Voice activation component using DayseAI logo
const TapToSpeak = ({ isRecording, toggleRecording, disabled }) => {
  return (
    <div className="tap-to-speak">
      <button 
        className={`tap-button ${isRecording ? 'recording' : ''}`}
        onClick={toggleRecording}
        disabled={disabled}
      >
        <img 
          src="/images/dayseai.png" 
          alt="DayseAI Logo" 
          className="tap-logo"
        />
      </button>
      <div className="tap-text">
        {isRecording ? 'Release to Stop' : 'Tap to Speak'}
      </div>
    </div>
  );
};

export default TapToSpeak;