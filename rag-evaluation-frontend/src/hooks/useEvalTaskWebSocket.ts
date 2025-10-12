/**
 * EvalScope任务WebSocket Hook
 */
import { useEffect, useState, useRef, useCallback } from 'react';
import type { WebSocketMessage } from '@/types/evalscope.types';
import { createTaskWebSocket } from '@/services/evalscope.service';

interface UseEvalTaskWebSocketReturn {
  messages: WebSocketMessage[];
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  sendMessage: (message: any) => void;
  reconnect: () => void;
}

/**
 * 用于EvalScope任务实时监控的WebSocket Hook
 */
export function useEvalTaskWebSocket(taskId: number): UseEvalTaskWebSocketReturn {
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    try {
      const ws = createTaskWebSocket(taskId);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log(`WebSocket connected for task ${taskId}`);
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setMessages((prev) => [...prev, message]);
          setLastMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        console.log(`WebSocket disconnected for task ${taskId}`);
        setIsConnected(false);

        // 自动重连（3秒后）
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('Attempting to reconnect...');
          connect();
        }, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

    } catch (error) {
      console.error('Failed to create WebSocket:', error);
    }
  }, [taskId]);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const reconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    connect();
  }, [connect]);

  useEffect(() => {
    connect();

    // 心跳检测
    const heartbeatInterval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 30000); // 每30秒发送一次心跳

    return () => {
      clearInterval(heartbeatInterval);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    messages,
    isConnected,
    lastMessage,
    sendMessage,
    reconnect
  };
}

export default useEvalTaskWebSocket;

