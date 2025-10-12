/**
 * 评测时间预估工具
 */

// 不同数据集的预估样本数量和复杂度
const DATASET_INFO: Record<string, {
  samples: number;
  complexity: 'low' | 'medium' | 'high';
  description: string;
}> = {
  // 基础数据集
  'mmlu': { samples: 14042, complexity: 'medium', description: '大规模多任务语言理解' },
  'cmmlu': { samples: 11528, complexity: 'medium', description: '中文多任务语言理解' },
  'ceval': { samples: 13948, complexity: 'medium', description: '中文语言模型综合能力评估' },
  'gsm8k': { samples: 1319, complexity: 'high', description: '小学数学应用题' },
  'humaneval': { samples: 164, complexity: 'high', description: '代码生成评测' },
  'arc': { samples: 7787, complexity: 'medium', description: 'AI推理挑战' },
  'hellaswag': { samples: 10042, complexity: 'low', description: '常识推理能力测试' },
  'bbh': { samples: 6511, complexity: 'high', description: '超难大模型基准测试' },
  
  // Arena数据集
  'gpqa_diamond': { samples: 198, complexity: 'high', description: 'GPQA钻石级别' },
  'general_arena': { samples: 100, complexity: 'high', description: '通用Arena对战' },
  
  // 默认值
  'default': { samples: 1000, complexity: 'medium', description: '标准数据集' }
};

// 不同复杂度的每样本预估时间（秒）
const COMPLEXITY_TIME: Record<string, {
  api: number;    // API模型
  local: number;  // 本地模型
}> = {
  'low': { api: 1, local: 3 },      // 简单任务：1-3秒/样本
  'medium': { api: 2, local: 5 },   // 中等任务：2-5秒/样本  
  'high': { api: 5, local: 10 }     // 复杂任务：5-10秒/样本
};

/**
 * 预估单个数据集的评测时间
 */
export function estimateDatasetTime(
  datasetName: string,
  modelType: 'api' | 'local' = 'api',
  sampleLimit?: number
): {
  estimatedSeconds: number;
  sampleCount: number;
  complexity: string;
  description: string;
} {
  const dataset = DATASET_INFO[datasetName] || DATASET_INFO['default'];
  const actualSamples = sampleLimit ? Math.min(sampleLimit, dataset.samples) : dataset.samples;
  const timePerSample = COMPLEXITY_TIME[dataset.complexity][modelType];
  
  return {
    estimatedSeconds: actualSamples * timePerSample,
    sampleCount: actualSamples,
    complexity: dataset.complexity,
    description: dataset.description
  };
}

/**
 * 预估多个数据集的总评测时间
 */
export function estimateTotalTime(
  datasets: string[],
  modelType: 'api' | 'local' = 'api',
  sampleLimit?: number,
  isParallel: boolean = false
): {
  totalSeconds: number;
  totalSamples: number;
  datasetDetails: Array<{
    name: string;
    estimatedSeconds: number;
    sampleCount: number;
    complexity: string;
    description: string;
  }>;
  parallelFactor: number;
} {
  const datasetDetails = datasets.map(dataset => ({
    name: dataset,
    ...estimateDatasetTime(dataset, modelType, sampleLimit)
  }));
  
  const totalSequentialTime = datasetDetails.reduce((sum, detail) => sum + detail.estimatedSeconds, 0);
  const totalSamples = datasetDetails.reduce((sum, detail) => sum + detail.sampleCount, 0);
  
  // 并行处理的加速因子（考虑API限制和资源竞争）
  let parallelFactor = 1;
  if (isParallel && datasets.length > 1) {
    if (modelType === 'api') {
      // API模型并行度受限于API速率限制
      parallelFactor = Math.min(datasets.length, 2); // 最多2倍加速
    } else {
      // 本地模型并行度受限于硬件资源
      parallelFactor = Math.min(datasets.length, 3); // 最多3倍加速
    }
  }
  
  return {
    totalSeconds: Math.ceil(totalSequentialTime / parallelFactor),
    totalSamples,
    datasetDetails,
    parallelFactor
  };
}

/**
 * 格式化时间预估结果为用户友好的字符串
 */
export function formatTimeEstimate(seconds: number): string {
  if (seconds < 60) {
    return `约${seconds}秒`;
  } else if (seconds < 3600) {
    const minutes = Math.ceil(seconds / 60);
    return `约${minutes}分钟`;
  } else if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.ceil((seconds % 3600) / 60);
    if (minutes === 0) {
      return `约${hours}小时`;
    }
    return `约${hours}小时${minutes}分钟`;
  } else {
    const days = Math.ceil(seconds / 86400);
    return `约${days}天`;
  }
}

/**
 * 生成详细的评测时间预估报告
 */
export function generateTimeEstimateReport(
  datasets: string[],
  modelType: 'api' | 'local' = 'api',
  sampleLimit?: number,
  isParallel: boolean = false
): string {
  const estimate = estimateTotalTime(datasets, modelType, sampleLimit, isParallel);
  
  let report = `📊 评测时间预估\n\n`;
  
  // 总体信息
  report += `🎯 总样本数: ${estimate.totalSamples.toLocaleString()}\n`;
  report += `⏱️ 预计耗时: ${formatTimeEstimate(estimate.totalSeconds)}\n`;
  
  if (isParallel && estimate.parallelFactor > 1) {
    const sequentialTime = estimate.totalSeconds * estimate.parallelFactor;
    report += `🚀 并行加速: ${estimate.parallelFactor}x (串行需${formatTimeEstimate(sequentialTime)})\n`;
  }
  
  report += `\n📋 数据集详情:\n`;
  
  // 数据集详情
  estimate.datasetDetails.forEach((detail, index) => {
    const complexityEmoji = {
      'low': '🟢',
      'medium': '🟡', 
      'high': '🔴'
    }[detail.complexity];
    
    report += `${index + 1}. ${detail.name}\n`;
    report += `   ${complexityEmoji} ${detail.sampleCount}样本 • ${formatTimeEstimate(detail.estimatedSeconds)}\n`;
  });
  
  // 性能提示
  report += `\n💡 优化建议:\n`;
  if (!sampleLimit || sampleLimit > 100) {
    report += `• 首次测试建议限制样本数(如50-100个)\n`;
  }
  if (datasets.length > 1 && !isParallel) {
    report += `• 多数据集可启用并行处理加速\n`;
  }
  if (modelType === 'local') {
    report += `• 本地模型建议使用GPU加速\n`;
  }
  
  return report;
}

/**
 * 检查评测时间是否过长并给出警告
 */
export function checkTimeWarning(
  datasets: string[],
  modelType: 'api' | 'local' = 'api',
  sampleLimit?: number
): {
  isLong: boolean;
  warning: string;
  suggestions: string[];
} {
  const estimate = estimateTotalTime(datasets, modelType, sampleLimit);
  const isLong = estimate.totalSeconds > 1800; // 超过30分钟
  
  let warning = '';
  const suggestions: string[] = [];
  
  if (isLong) {
    warning = `⚠️ 预计评测时间较长(${formatTimeEstimate(estimate.totalSeconds)})`;
    
    if (!sampleLimit) {
      suggestions.push('建议设置样本数限制(如100个)进行快速测试');
    }
    
    if (datasets.length > 1) {
      suggestions.push('可以分批评测或启用并行处理');
    }
    
    if (estimate.totalSamples > 10000) {
      suggestions.push('大规模评测建议在服务器环境运行');
    }
    
    suggestions.push('评测期间请保持网络稳定，避免中断');
  }
  
  return {
    isLong,
    warning,
    suggestions
  };
}
