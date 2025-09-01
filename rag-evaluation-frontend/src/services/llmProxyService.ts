export async function testLLMConnectivity({ baseUrl, apiKey, modelName, additionalParams }: {
  baseUrl: string;
  apiKey: string;
  modelName: string;
  additionalParams?: any;
}) {
  const resp = await fetch('/api/llm/llm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      llm_url: baseUrl,
      api_key: apiKey,
      payload: {
        model: modelName,
        messages: [
          { role: 'user', content: '你好' }
        ],
        ...(additionalParams || {})
      }
    })
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || err.detail || '后端转发请求失败');
  }
  const data = await resp.json();
  return data.choices?.[0]?.message?.content || JSON.stringify(data);
} 