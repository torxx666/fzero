import { useState, useRef, useCallback } from 'react';

export const useRecorder = (onChunk?: (blob: Blob) => void) => {
    const [isRecording, setIsRecording] = useState(false);
    const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
    const [stream, setStream] = useState<MediaStream | null>(null); // New: Expose stream
    const mediaRecorder = useRef<MediaRecorder | null>(null);
    const audioChunks = useRef<Blob[]>([]);
    const intervalRef = useRef<number | null>(null);

    const stopRecording = useCallback(() => {
        if (mediaRecorder.current && mediaRecorder.current.state !== 'inactive') {
            mediaRecorder.current.stop();
            mediaRecorder.current.stream.getTracks().forEach(track => track.stop());
        }
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
        setIsRecording(false);
        setStream(null); // Clear stream
    }, []);

    const startRecording = useCallback(async () => {
        setAudioBlob(null);
        try {
            const newStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            setStream(newStream); // Set stream

            const createAndStartRecorder = () => {
                const recorder = new MediaRecorder(newStream, { mimeType: 'audio/webm' });
                const localChunks: Blob[] = [];

                recorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        localChunks.push(event.data);
                        audioChunks.current.push(event.data);
                    }
                };

                recorder.onstop = () => {
                    if (localChunks.length > 0) {
                        const blob = new Blob(localChunks, { type: 'audio/webm' });
                        if (onChunk) onChunk(blob);
                    }
                };

                recorder.start();
                mediaRecorder.current = recorder;
            };

            audioChunks.current = [];
            createAndStartRecorder();
            setIsRecording(true);

        } catch (err) {
            console.error("Error accessing microphone:", err);
        }

    }, [onChunk]);

    return { isRecording, audioBlob, startRecording, stopRecording, stream };
};
