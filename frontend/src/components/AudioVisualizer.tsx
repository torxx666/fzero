import { useEffect, useRef } from 'react';

interface AudioVisualizerProps {
    stream: MediaStream | null;
    isRecording: boolean;
}

const AudioVisualizer = ({ stream, isRecording }: AudioVisualizerProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animationRef = useRef<number>();
    const analyserRef = useRef<AnalyserNode>();
    const contextRef = useRef<AudioContext>();

    useEffect(() => {
        if (!stream || !isRecording || !canvasRef.current) return;

        // Initialize Audio Context
        if (!contextRef.current) {
            contextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }

        const audioContext = contextRef.current;
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256; // Controls resolution (bars count)
        analyser.smoothingTimeConstant = 0.8; // Smoothing

        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);
        analyserRef.current = analyser;

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const draw = () => {
            if (!isRecording) return;

            animationRef.current = requestAnimationFrame(draw);
            analyser.getByteFrequencyData(dataArray);

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Circular Visualizer logic or Bar logic?
            // Let's do a cool symmetrical bar graph from center
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const radius = 50; // Base circle radius

            // Draw Center Circle (Mic replacement)
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius - 5, 0, 2 * Math.PI);
            ctx.fillStyle = '#ef4444'; // Red-500
            ctx.shadowBlur = 20;
            ctx.shadowColor = '#ef4444';
            ctx.fill();

            // Draw Bars sticking out
            const bars = 60; // Number of bars
            const step = (Math.PI * 2) / bars;

            for (let i = 0; i < bars; i++) {
                // Map frequency data to bars
                // Use lower frequencies for more movement
                const value = dataArray[i * 2] || 0;
                const barHeight = (value / 255) * 100; // Max height 100px

                const angle = i * step;

                // Start point on circle edge
                const x1 = centerX + Math.cos(angle) * radius;
                const y1 = centerY + Math.sin(angle) * radius;

                // End point
                const x2 = centerX + Math.cos(angle) * (radius + barHeight);
                const y2 = centerY + Math.sin(angle) * (radius + barHeight);

                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.lineWidth = 4;
                ctx.strokeStyle = `hsla(${0 + (value / 255) * 50}, 100%, 50%, 0.8)`; // Red to Orange gradient
                ctx.lineCap = 'round';
                ctx.stroke();
            }
        };

        draw();

        return () => {
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
            source.disconnect();
            // Do not close AudioContext immediately as it might be reused or costly
        };
    }, [stream, isRecording]);

    return (
        <canvas
            ref={canvasRef}
            width={400}
            height={400}
            className="w-full h-full max-w-[300px] max-h-[300px]"
        />
    );
};

export default AudioVisualizer;
