import { useState, useRef, useCallback } from 'react';

export const useRecorder = (onChunk?: (blob: Blob) => void) => {
    const [isRecording, setIsRecording] = useState(false);
    const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
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
    }, []);

    const startRecording = useCallback(async () => {
        setAudioBlob(null);
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        const createAndStartRecorder = () => {
            const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            const localChunks: Blob[] = [];

            recorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    localChunks.push(event.data);
                    audioChunks.current.push(event.data); // Keep global for final blob
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

        // Restart recorder every 5 seconds to get valid standalone files (with headers)
        intervalRef.current = window.setInterval(() => {
            if (mediaRecorder.current && mediaRecorder.current.state === 'recording') {
                mediaRecorder.current.stop();
                createAndStartRecorder();
            }
        }, 5000);

    }, [onChunk]);

    return { isRecording, audioBlob, startRecording, stopRecording };
};
