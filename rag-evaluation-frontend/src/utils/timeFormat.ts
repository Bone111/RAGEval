/**
 * 时间格式化工具函数
 */

/**
 * 将秒数格式化为易读的时间字符串
 * @param seconds 秒数
 * @returns 格式化后的时间字符串
 */
export function formatDuration(seconds: number): string {
  if (seconds <= 0) {
    return '0秒';
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;

  const parts: string[] = [];

  if (hours > 0) {
    parts.push(`${hours}小时`);
  }

  if (minutes > 0) {
    parts.push(`${minutes}分钟`);
  }

  if (remainingSeconds > 0 || parts.length === 0) {
    parts.push(`${remainingSeconds}秒`);
  }

  return parts.join('');
}

/**
 * 将毫秒数格式化为易读的时间字符串
 * @param milliseconds 毫秒数
 * @returns 格式化后的时间字符串
 */
export function formatDurationFromMs(milliseconds: number): string {
  return formatDuration(Math.round(milliseconds / 1000));
}

/**
 * 计算两个日期之间的时间差并格式化
 * @param startTime 开始时间
 * @param endTime 结束时间（可选，默认为当前时间）
 * @returns 格式化后的时间差字符串
 */
export function formatTimeDiff(startTime: string | Date, endTime?: string | Date): string {
  const start = new Date(startTime);
  const end = endTime ? new Date(endTime) : new Date();
  
  const diffMs = end.getTime() - start.getTime();
  return formatDurationFromMs(diffMs);
}

/**
 * 格式化运行时间（用于实时显示）
 * @param startTime 开始时间
 * @param endTime 结束时间（可选）
 * @returns 格式化后的运行时间
 */
export function formatRunningTime(startTime: string | Date, endTime?: string | Date): string {
  try {
    return formatTimeDiff(startTime, endTime);
  } catch (error) {
    return 'N/A';
  }
}

/**
 * 获取时间单位的简短描述
 * @param seconds 秒数
 * @returns 简短的时间描述
 */
export function getTimeDescription(seconds: number): string {
  if (seconds < 60) {
    return '不到1分钟';
  } else if (seconds < 3600) {
    const minutes = Math.ceil(seconds / 60);
    return `约${minutes}分钟`;
  } else if (seconds < 86400) {
    const hours = Math.ceil(seconds / 3600);
    return `约${hours}小时`;
  } else {
    const days = Math.ceil(seconds / 86400);
    return `约${days}天`;
  }
}
