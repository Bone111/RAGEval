import React, { useState, useEffect } from 'react';
import { Card, Button, Upload, Spin, Form, InputNumber, Select, Radio, Divider, message, Table, Progress, Alert, Checkbox, Slider, Modal, Tooltip, Input, Badge, Space, Collapse, Typography, Empty, Row, Col } from 'antd';
import { UploadOutlined, FileTextOutlined, CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined, FullscreenOutlined, DeleteOutlined, EyeOutlined, WarningOutlined, InfoCircleOutlined, QuestionCircleOutlined, SettingOutlined } from '@ant-design/icons';
import { mineruService } from '../../services/mineruService';
import MinerUErrorAlert from '../../components/MinerUErrorAlert';
import { useNavigate } from 'react-router-dom';
import { authService } from '../../services/auth.service';
import { questionGeneratorService, SplitterType, FailedRequestRecord } from '../../services/QuestionGeneratorService';
import { TextChunk, GenerationParams, GeneratedQA, ProgressInfo } from '../../types/question-generator';
import styles from './QuestionGeneration.module.css';
import { ConfigManager, ModelConfig } from '../../utils/configManager';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const { Option } = Select;
const { Column } = Table;

interface QuestionGenerationContentProps {
  datasetId: string;
  onGenerationComplete?: () => void;
}

// 新增类型，用于保存文件内容
interface FileContent {
  name: string;
  content: string;
}

const QuestionGenerationContent: React.FC<QuestionGenerationContentProps> = ({ datasetId, onGenerationComplete }) => {
  const navigate = useNavigate();
  const [form] = Form.useForm();

  const [isConfigured, setIsConfigured] = useState(false);
  const [isCheckingConfig, setIsCheckingConfig] = useState(true); // 添加配置检查状态
  const [fileList, setFileList] = useState<any[]>([]);
  const [chunks, setChunks] = useState<TextChunk[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedQAs, setGeneratedQAs] = useState<GeneratedQA[]>([]);
  const [progress, setProgress] = useState<ProgressInfo>({
    totalChunks: 0,
    completedChunks: 0,
    totalQAPairs: 0,
    generatedQAPairs: 0,
    isCompleted: false
  });
  const [currentTab, setCurrentTab] = useState<'upload' | 'chunks' | 'generate' | 'results'>('upload');
  const [chunkSize, setChunkSize] = useState<number>(2048);
  const [isRechunking, setIsRechunking] = useState(false);

  // 修改状态，保存文件内容而不是File对象
  const [uploadedContents, setUploadedContents] = useState<FileContent[]>([]);
  const [parsedFiles, setParsedFiles] = useState<any[]>([]); // 保存每个文件的解析状态和内容
  const [previewModalVisible, setPreviewModalVisible] = useState(false); // 预览弹窗
  const [selectedPreviewFile, setSelectedPreviewFile] = useState<any>(null); // 选中的预览文件

  // 预览单个文件的弹窗
  const [filePreviewModalVisible, setFilePreviewModalVisible] = useState(false);
  const [filePreviewPath, setFilePreviewPath] = useState<string | null>(null);
  const [filePreviewType, setFilePreviewType] = useState<string | null>(null);
  const [filePreviewContent, setFilePreviewContent] = useState<string | null>(null);

  // 预览按钮点击时
  const handlePreview = (fpath: string) => {
    // 如果 fpath 不是绝对地址，则加上 window.location.origin
    let fullPath = fpath;
    if (!/^https?:\/\//.test(fpath)) {
      // fullPath = window.location.origin + fpath;
    }
    console.log('预览文件地址:', fullPath); // 打印完整预览地址
    setFilePreviewPath(fullPath);
    setFilePreviewType(fullPath.split('.').pop()?.toLowerCase() || '');
    setFilePreviewContent(null);
    setFilePreviewModalVisible(true);
    // 对于 txt/json/md 先 fetch 内容
    if (/\.(json|txt|md)$/i.test(fullPath)) {
      fetch(fullPath)
        .then(res => res.text())
        .then(text => setFilePreviewContent(text))
        .catch(() => setFilePreviewContent('无法加载内容'));
    }
  };

  // 预览渲染
  const renderFilePreviewModal = () => {
    if (!filePreviewPath) return null;
    if (/\.(png|jpg|jpeg|gif)$/i.test(filePreviewPath)) {
      return (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <img src={filePreviewPath} alt="" style={{ maxWidth: '90%', maxHeight: 600, borderRadius: 8, boxShadow: '0 2px 16px #eee', border: '1px solid #eee' }} />
        </div>
      );
    }
    if (/\.(pdf)$/i.test(filePreviewPath)) {
      return (
        <iframe
          src={filePreviewPath}
          title="PDF预览"
          style={{ width: '100%', height: 700, border: 'none', borderRadius: 8, boxShadow: '0 2px 16px #eee' }}
        />
      );
    }
    if (/\.(md)$/i.test(filePreviewPath)) {
      return (
        <div style={{ background: '#fff', padding: 24, borderRadius: 8, height: 700, overflow: 'auto', fontFamily: 'inherit', boxShadow: '0 2px 16px #eee' }}>
          {filePreviewContent ? (
            <ReactMarkdown children={filePreviewContent} remarkPlugins={[remarkGfm]} />
          ) : '加载中...'}
        </div>
      );
    }
    if (/\.(txt)$/i.test(filePreviewPath)) {
      return (
        <div style={{ background: '#f6f8fa', padding: 24, borderRadius: 8, height: 700, overflow: 'auto', fontFamily: 'monospace', boxShadow: '0 2px 16px #eee' }}>
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0 }}>{filePreviewContent ?? '加载中...'}</pre>
        </div>
      );
    }
    if (/\.(json)$/i.test(filePreviewPath)) {
      let formatted = '';
      try {
        formatted = filePreviewContent ? JSON.stringify(JSON.parse(filePreviewContent), null, 2) : '';
      } catch {
        formatted = filePreviewContent || '';
      }
      return (
        <div style={{ background: '#23272e', color: '#fff', padding: 24, borderRadius: 8, height: 700, overflow: 'auto', fontFamily: 'monospace', boxShadow: '0 2px 16px #eee' }}>
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0 }}>{formatted || '加载中...'}</pre>
        </div>
      );
    }
    return (
      <div style={{ textAlign: 'center', color: '#888', padding: 48 }}>
        暂不支持该类型文件的预览
      </div>
    );
  };

  // 添加分割方式状态
  const [splitterType, setSplitterType] = useState<SplitterType>('recursive');

  // 在 state 区域添加分割策略模式
  const [splitMode, setSplitMode] = useState<'langchain' | 'llamaindex'>('langchain');

  // 添加新状态用于展开/折叠功能和模态窗口
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());
  const [modalVisible, setModalVisible] = useState(false);
  const [currentChunk, setCurrentChunk] = useState<TextChunk | null>(null);

  // 添加选择行状态
  const [selectedQAKeys, setSelectedQAKeys] = useState<React.Key[]>([]);

  // 添加提示词预览功能
  const [promptTemplate, setPromptTemplate] = useState<string>('');
  const [promptModalVisible, setPromptModalVisible] = useState(false);

  // 在组件的状态部分添加自定义提示词模板的状态
  const [customPromptTemplate, setCustomPromptTemplate] = useState<string>('');
  const [useCustomPrompt, setUseCustomPrompt] = useState(false);
  
  // 添加查看原始响应的状态
  const [rawResponseModalVisible, setRawResponseModalVisible] = useState(false);
  const [currentRawResponse, setCurrentRawResponse] = useState<string>('');
  
  // 添加失败记录列表状态
  const [failedRequestsModalVisible, setFailedRequestsModalVisible] = useState(false);
  const [failedRequests, setFailedRequests] = useState<FailedRequestRecord[]>([]);

  const [availableModels, setAvailableModels] = useState<ModelConfig[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>('');

  // 新增解析状态 state
  const [parsingStatus, setParsingStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [parsingError, setParsingError] = useState<string>('');
  const [mineruError, setMineruError] = useState<any>(null);
  const [mineruConfigStatus, setMineruConfigStatus] = useState<any>(null);
  const [checkingMineruConfig, setCheckingMineruConfig] = useState(true); // 初始为true，避免闪烁
  
  // 解析方式选择状态
  const [parserMode, setParserMode] = useState<'auto' | 'mineru' | 'local'>('auto');

  // 监听解析模式变化，重置解析状态
  useEffect(() => {
    // 当解析模式改变时，重置解析状态
    if (parsingStatus !== 'idle' || parsedFiles.length > 0) {
      setParsingStatus('idle');
      setParsedFiles([]);
      setParsingError('');
      setMineruError(null);
    }
  }, [parserMode]);

  // 添加加载可用模型的函数
  const loadAvailableModels = async () => {
    const configManager = ConfigManager.getInstance();
    const models = await configManager.getAllConfigs<ModelConfig>('model');
    setAvailableModels(models);
    if (models.length > 0) {
      setSelectedModelId(models[0].id);
    }
  };

  // 检查MinerU配置状态
  const checkMineruConfig = async () => {
    setCheckingMineruConfig(true);
    try {
      const status = await mineruService.checkConfigStatus();
      console.log('MinerU配置状态:', status);
      setMineruConfigStatus(status);
    } catch (error: any) {
      console.error('检查MinerU配置失败:', error);
      
      // 如果是认证错误，说明用户未登录，不显示错误
      if (error?.response?.status === 401 || error?.message?.includes('认证')) {
        const fallbackStatus = {
          has_config: false,
          api_status: 'unknown' as const,
          error_message: '需要登录后检查配置',
          config_source: 'none' as const
        };
        console.log('设置认证错误状态:', fallbackStatus);
        setMineruConfigStatus(fallbackStatus);
      } else {
        const fallbackStatus = {
          has_config: false,
          api_status: 'error' as const,
          error_message: '检查配置失败',
          config_source: 'none' as const
        };
        console.log('设置错误状态:', fallbackStatus);
        setMineruConfigStatus(fallbackStatus);
      }
    } finally {
      setCheckingMineruConfig(false);
    }
  };

  // 在组件加载时获取可用模型和检查MinerU配置
  useEffect(() => {
    loadAvailableModels();
    checkMineruConfig();
  }, []);

  // 监听配置变化事件，重新检查MinerU配置
  useEffect(() => {
    const handleConfigChange = () => {
      console.log('检测到配置变化，重新检查MinerU配置');
      checkMineruConfig();
    };

    window.addEventListener('configChanged', handleConfigChange);
    
    return () => {
      window.removeEventListener('configChanged', handleConfigChange);
    };
  }, []);

  // 监听大模型配置变化事件，重新检查配置状态
  useEffect(() => {
    const handleModelConfigChange = () => {
      console.log('检测到大模型配置变化，重新检查配置状态');
      const checkLLMConfig = async () => {
        try {
          setIsCheckingConfig(true);
          const configManager = ConfigManager.getInstance();
          const configs = await configManager.getAllConfigs<ModelConfig>('model');
          setIsConfigured(configs.length > 0);
        } catch (error) {
          console.error('检查LLM配置失败:', error);
          setIsConfigured(false);
        } finally {
          setIsCheckingConfig(false);
        }
      };
      checkLLMConfig();
    };

    window.addEventListener('configChanged', handleModelConfigChange);
    
    return () => {
      window.removeEventListener('configChanged', handleModelConfigChange);
    };
  }, []);

  useEffect(() => {
    // 使用ConfigManager检查LLM配置
    const checkLLMConfig = async () => {
      try {
        setIsCheckingConfig(true);
        const configManager = ConfigManager.getInstance();
        const configs = await configManager.getAllConfigs<ModelConfig>('model');
        setIsConfigured(configs.length > 0);
      } catch (error) {
        console.error('检查LLM配置失败:', error);
        setIsConfigured(false);
      } finally {
        setIsCheckingConfig(false);
      }
    };
    
    checkLLMConfig();
  }, []);

  // 在组件初始化时，获取默认提示词模板
  useEffect(() => {
    // 获取默认提示词模板
    const defaultTemplate = questionGeneratorService.getDefaultPromptTemplate();
    setCustomPromptTemplate(defaultTemplate);
  }, []);

  const handleFileUpload = async (info: any) => {
    let fileList = [...info.fileList];
    fileList = fileList.slice(-1);
    setFileList(fileList);

    if (info.file.status === 'done') {
      message.success(`${info.file.name} 上传成功`);
    } else if (info.file.status === 'error') {
      message.error(`${info.file.name} 上传失败`);
    }

    if (fileList.length === 0) return;

    setParsingStatus('loading');
    setParsingError('');
    setParsedFiles([]);

    try {
      const files = fileList.map(file => file.originFileObj);
      
      // 根据解析方式选择不同的API
      if (parserMode === 'local') {
        // 使用本地解析
        const formData = new FormData();
        formData.append('file', files[0]);
        formData.append('use_mineru', 'false');
        
        const response = await fetch('/api/v1/file-parser/parse-file/', {
          method: 'POST',
          body: formData,
          headers: {
            'Authorization': `Bearer ${authService.getToken() || ''}`
          }
        });
        
        const data = await response.json();
        if (data.success) {
          // 构造与MinerU格式兼容的返回数据
          const parsedFile = {
            filename: data.filename,
            success: true,
            md_text: data.md_content,
            extracted_files: [],
            error_msg: null
          };
          setParsedFiles([parsedFile]);
          setParsingStatus('success');
          
          // 本地解析成功后自动生成分块并跳转
          message.success('文件解析成功，正在生成文本分块...');
          const contents = [{ name: data.filename, content: data.md_content }];
          setUploadedContents(contents);
          
          questionGeneratorService.processContentFiles(contents).then(processedChunks => {
            setChunks(processedChunks);
            setCurrentTab('chunks');
            message.success('文本分块完成，请确认分块设置');
          }).catch(error => {
            message.error(`生成文本分块失败: ${(error as Error).message}`);
            setCurrentTab('chunks'); // 即使分块失败也跳转，让用户看到错误
          });
        } else {
          setParsingStatus('error');
          let errorMessage = data.detail || '本地解析失败';
          
          // 检查是否是依赖缺失错误
          if (typeof errorMessage === 'string' && errorMessage.includes('未安装')) {
            errorMessage = `本地解析失败：${errorMessage}\n\n建议：\n1. 安装缺失的依赖库\n2. 或选择使用MinerU在线解析`;
          }
          
          setParsingError(errorMessage);
        }
      } else {
        // 使用MinerU解析（auto或mineru模式）
        const formData = new FormData();
        formData.append('file', files[0]);
        formData.append('is_ocr', 'true');
        formData.append('enable_formula', 'false');
        
        const response = await fetch('/api/v1/mineru/mineru-upload-and-parse', {
          method: 'POST',
          body: formData,
          headers: {
            'Authorization': `Bearer ${authService.getToken() || ''}`
          }
        });
        
        const data = await response.json();
        if (data && data.files) {
          setParsedFiles(data.files);
          setParsingStatus('success');
          
          // MinerU解析成功，不自动跳转，让用户查看解析结果
          message.success('文件解析成功！可以点击"处理文件"按钮进行预览和切片');
        } else {
          setParsingStatus('error');
          setParsingError(data.error || 'mineru解析失败');
        }
      }
    } catch (err: any) {
      setParsingStatus('error');
      
      // 如果是MinerU解析失败且是auto模式，尝试本地解析
      if (parserMode === 'auto' && err.response?.status === 401) {
        try {
          message.warning('MinerU密钥无效，尝试使用本地解析...');
          const files = fileList.map(file => file.originFileObj);
          const formData = new FormData();
          formData.append('file', files[0]);
          formData.append('use_mineru', 'false');
          
          const response = await fetch('/api/v1/file-parser/parse-file/', {
            method: 'POST',
            body: formData,
            headers: {
              'Authorization': `Bearer ${authService.getToken() || ''}`
            }
          });
          
          const data = await response.json();
          if (data.success) {
            const parsedFile = {
              filename: data.filename,
              success: true,
              md_text: data.md_content,
              extracted_files: [],
              error_msg: null
            };
            setParsedFiles([parsedFile]);
            setParsingStatus('success');
            message.success('已自动切换到本地解析，正在生成文本分块...');
            
            const contents = [{ name: data.filename, content: data.md_content }];
            setUploadedContents(contents);
            
            questionGeneratorService.processContentFiles(contents).then(processedChunks => {
              setChunks(processedChunks);
              setCurrentTab('chunks');
              message.success('文本分块完成，请确认分块设置');
            }).catch(error => {
              message.error(`生成文本分块失败: ${(error as Error).message}`);
              setCurrentTab('chunks'); // 即使分块失败也跳转，让用户看到错误
            });
            return;
          }
        } catch (localErr) {
          console.error('本地解析也失败:', localErr);
        }
      }
      
      const parsedError = mineruService.parseError(err);
      setMineruError(parsedError);
      setParsingError(parsedError.message);
    }
  };

  const handleProcessFiles = () => {
    if (parsedFiles.length === 0) {
      message.warning('请先上传并解析文件');
      return;
    }
    setPreviewModalVisible(true);
  };

  // 只对选中的文件内容进行切片
  const handleNextStep = async () => {
    if (!selectedPreviewFile) {
      message.warning('请先选择一个文件进行切片');
      return;
    }
    setPreviewModalVisible(false);

    // 只对选中的 extracted_files 文件内容进行切片
    let content = '';
    const { fpath, filename } = selectedPreviewFile;
    if (/\.(md|txt|json)$/i.test(fpath)) {
      try {
        const res = await fetch(fpath);
        content = await res.text();
      } catch (e) {
        message.error('读取文件内容失败');
        return;
      }
    } else {
      message.error('暂不支持二进制文件的切片');
      return;
    }
    const contents = [{ name: filename || (fpath && fpath.split('/')?.pop()) || 'file', content }];
    setUploadedContents(contents);
    // 使用默认分块大小进行初始分块
    questionGeneratorService.processContentFiles(contents).then(processedChunks => {
      setChunks(processedChunks);
      setCurrentTab('chunks');
      message.success('文件处理完成，请确认文本分块');
    }).catch(error => {
      message.error(`处理文件失败: ${(error as Error).message}`);
    });
  };

 

  // 组件卸载时清理轮询
  useEffect(() => {
    return () => {
      // 删除与 /api/v1/convert-to-md-async 相关的 state、pollingInterval、pollProgress、conversionProgress、uploadAndConvertToMdAsync、uploadAndConvertToMdWithProgress、uploadAndConvertToMd
    };
  }, []);

  // 修改重新分块功能，传入分割类型
  const handleRechunk = async () => {
    if (uploadedContents.length === 0) {
      message.warning('没有可用的文件内容进行重新分块');
      return;
    }

    setIsRechunking(true);

    try {
      let processedChunks = [];
      if (splitMode === 'langchain') {
        processedChunks = await questionGeneratorService.processContentFiles(uploadedContents, chunkSize, splitterType);
      } else if (splitMode === 'llamaindex') {
        // 这里调用 LlamaIndex 分块实现（可用后端API，或前端占位）
        processedChunks = await questionGeneratorService.processContentFilesWithLlamaIndex(uploadedContents, chunkSize);
      }
      setChunks(processedChunks);
      message.success('分块完成');
    } catch (error) {
      message.error(`重新分块失败: ${(error as Error).message}`);
    } finally {
      setIsRechunking(false);
    }
  };

  const handleChunkSelectionChange = (chunkId: string, selected: boolean) => {
    setChunks(prevChunks =>
      prevChunks.map(chunk =>
        chunk.id === chunkId ? { ...chunk, selected } : chunk
      )
    );
  };

  // 添加处理提示词更改的函数
  const handlePromptChange = (value: string) => {
    setCustomPromptTemplate(value);
  };

  // 修改预览提示词的函数，使其使用自定义提示词
  const previewPrompt = () => {
    if (chunks.filter(c => c.selected).length === 0) {
      message.warning('请至少选择一个文本块');
      return;
    }

    const values = form.getFieldsValue();
    const params: GenerationParams = {
      count: values.count,
      difficulty: values.difficulty,
      questionTypes: values.questionTypes,
      maxTokens: values.maxTokens
    };

    // 获取第一个选中的文本块作为示例
    const sampleChunk = chunks.find(c => c.selected);
    if (sampleChunk) {
      // 使用服务中的buildPrompt方法获取实际的提示词，传入自定义模板
      const promptPreview = questionGeneratorService.previewPrompt(
        sampleChunk.content,
        params,
        useCustomPrompt ? customPromptTemplate : undefined
      );
      setPromptTemplate(promptPreview);
      setPromptModalVisible(true);
    }
  };

  // 修改生成问答对的函数
  const handleGenerateQA = async () => {
    try {
      await form.validateFields();

      if (!selectedModelId) {
        message.error('请选择大模型');
        return;
      }

      if (!datasetId) {
        message.error('数据集ID不能为空');
        return;
      }

      const values = form.getFieldsValue();
      const params: GenerationParams = {
        count: values.count,
        difficulty: values.difficulty,
        questionTypes: values.questionTypes,
        maxTokens: values.maxTokens,
        concurrency: values.concurrency
      };

      setIsGenerating(true);
      setCurrentTab('generate');
      setGeneratedQAs([]);

      // 开始生成问答对，传入选中的模型ID
      await questionGeneratorService.generateQAPairs(
        params,
        datasetId,
        selectedModelId,
        (newProgress, newQAs) => {
          setProgress(newProgress);
          if (newQAs) {
            setGeneratedQAs(prev => [...prev, ...newQAs]);
          }

          if (newProgress.isCompleted) {
            setCurrentTab('results');
            setIsGenerating(false);
          }
        },
        useCustomPrompt ? customPromptTemplate : undefined
      );
    } catch (error) {
      message.error(`生成问答对失败: ${(error as Error).message}`);
      setIsGenerating(false);
    }
  };

  const handleStopGeneration = () => {
    questionGeneratorService.stopGeneration();
    message.info('正在停止生成...');
    // 设置一个短暂的延迟，让用户看到停止消息
    setTimeout(() => {
      setCurrentTab('results');
      setIsGenerating(false);
    }, 1000);
  };

  const handleFinish = () => {
    message.success('问答对已保存到数据集');
    if (onGenerationComplete) {
      onGenerationComplete();
    }
    navigate(`/datasets/${datasetId}`);
  };

  // 添加用于处理展开/折叠的函数
  const toggleChunkExpand = (chunkId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // 防止触发点击卡片的事件
    setExpandedChunks(prev => {
      const next = new Set(prev);
      if (next.has(chunkId)) {
        next.delete(chunkId);
      } else {
        next.add(chunkId);
      }
      return next;
    });
  };

  // 添加用于显示模态窗口的函数
  const showChunkModal = (chunk: TextChunk) => {
    setCurrentChunk(chunk);
    setModalVisible(true);
  };

  // 添加选择行处理函数
  const handleQASelectChange = (selectedRowKeys: React.Key[]) => {
    setSelectedQAKeys(selectedRowKeys);
  };

  // 添加处理已选项的函数
  const handleDeleteSelectedQAs = () => {
    if (selectedQAKeys.length === 0) {
      message.warning('请至少选择一项');
      return;
    }

    Modal.confirm({
      title: `确定要删除所选的 ${selectedQAKeys.length} 个问答对吗?`,
      content: '删除后不会影响已保存到数据集的问答对',
      onOk: () => {
        const filteredQAs = generatedQAs.filter(
          qa => !selectedQAKeys.includes(qa.id)
        );
        setGeneratedQAs(filteredQAs);
        setSelectedQAKeys([]);
        message.success(`已删除 ${selectedQAKeys.length} 个问答对`);
      }
    });
  };

  // 在表单下方添加提示词模板编辑区域
  const renderPromptTemplateEditor = () => (
    <div className={styles.promptTemplateEditor}>
      {/* <Divider>提示词模板设置</Divider> */}
      <div className={styles.promptTemplateHeader}>
        <Checkbox
          checked={useCustomPrompt}
          onChange={(e) => setUseCustomPrompt(e.target.checked)}
        >
          使用自定义提示词模板
        </Checkbox>
        {useCustomPrompt && (
          <Button
            size="small"
            onClick={() => {
              const defaultTemplate = questionGeneratorService.getDefaultPromptTemplate();
              setCustomPromptTemplate(defaultTemplate);
            }}
          >
            恢复默认
          </Button>
        )}
      </div>
      {useCustomPrompt && (
        <div className={styles.promptTemplateContent}>
          <Alert
            message="提示词模板说明"
            description={
              <>
                <p>在模板中可以使用以下占位符：</p>
                <ul>
                  <li><code>{'{{text}}'}</code> - 文本块内容</li>
                  <li><code>{'{{count}}'}</code> - 每块生成的问题数量</li>
                </ul>
                <p>修改提示词模板可能会影响解析，请确保输出格式保持一致。</p>
              </>
            }
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Input.TextArea
            value={customPromptTemplate}
            onChange={(e) => handlePromptChange(e.target.value)}
            autoSize={{ minRows: 6, maxRows: 12 }}
            disabled={!useCustomPrompt}
          />
        </div>
      )}
    </div>
  );

  // 支持多类型文件预览
  const renderExtractedFilePreview = (filePath: string) => {
    if (/\.(png|jpg|jpeg|gif)$/i.test(filePath)) {
      return <img src={filePath} alt="" style={{ maxWidth: 400, maxHeight: 400, margin: 8 }} />;
    }
    if (/\.(pdf)$/i.test(filePath)) {
      return (
        <iframe
          src={filePath}
          title="PDF预览"
          style={{ width: 400, height: 400, border: '1px solid #eee', margin: 8 }}
        />
      );
    }
    if (/\.(md)$/i.test(filePath)) {
      return (
        <iframe
          src={filePath}
          title="Markdown预览"
          style={{ width: 400, height: 400, border: '1px solid #eee', margin: 8 }}
        />
      );
    }
    if (/\.(txt)$/i.test(filePath)) {
      return (
        <iframe
          src={filePath}
          title="文本预览"
          style={{ width: 400, height: 400, border: '1px solid #eee', margin: 8 }}
        />
      );
    }
    // 其他类型
    return <span style={{ margin: 8 }}>{filePath.split('/').pop()}</span>;
  };

  // 新增：清理缓存确认弹窗状态
  const [clearCacheModalVisible, setClearCacheModalVisible] = useState(false);

  // 修改清理缓存函数，弹出确认框
  const handleClearMineruCache = async () => {
    setClearCacheModalVisible(true);
  };

  const doClearMineruCache = async () => {
    try {
      const resp = await fetch('/api/v1/mineru/clear-mineru-cache', { method: 'POST' });
      const data = await resp.json();
      if (data.success) {
        message.success('mineru解析缓存已清理');
        setParsedFiles([]);
        setParsingStatus('idle');
      } else {
        message.error(data.error || '清理缓存失败');
      }
    } catch (e) {
      message.error('清理缓存请求失败');
    } finally {
      setClearCacheModalVisible(false);
    }
  };

  const renderUploadContent = () => (
    <Card title="上传文件" className={styles.card}>
      <div className={styles.uploadSection}>
        {/* 配置检查状态 */}
        {(isCheckingConfig || checkingMineruConfig) && (
          <Alert
            message="正在检查配置状态..."
            description="请稍候，正在检查大模型API和MinerU配置状态"
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
          />
        )}
        
        {/* 大模型配置状态提示 */}
        {!isCheckingConfig && !isConfigured && (
          <Alert
            message="未配置大模型API"
            description="请先配置大模型API以进行问题生成"
            type="warning"
            action={
              <Button 
                type="primary" 
                size="small"
                onClick={() => navigate('/user/settings')}
              >
                立即配置
              </Button>
            }
            showIcon
            style={{ marginBottom: 24 }}
          />
        )}
        
        
        {/* 解析方式选择 */}
        <Card style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 16 }}>
            <Typography.Text strong>选择解析方式：</Typography.Text>
          </div>
          <Radio.Group 
            value={parserMode} 
            onChange={(e) => setParserMode(e.target.value)}
            style={{ marginBottom: 16 }}
          >
            <Radio value="auto">
              <div>
                <div style={{ fontWeight: 500 }}>自动选择（推荐）</div>
                <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                  优先使用MinerU，密钥无效时自动切换到本地解析
                </div>
              </div>
            </Radio>
            <Radio value="mineru">
              <div>
                <div style={{ fontWeight: 500 }}>MinerU在线解析</div>
                <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                  使用MinerU API进行高质量文档解析，需要有效密钥
                </div>
              </div>
            </Radio>
            <Radio value="local">
              <div>
                <div style={{ fontWeight: 500 }}>本地解析</div>
                <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                  使用本地解析库，无需API密钥，支持基础格式
                </div>
              </div>
            </Radio>
          </Radio.Group>
          
          {/* 根据选择显示不同提示 */}
          {parserMode === 'auto' && (
            <Alert
              message="自动模式说明"
              description="系统会优先尝试MinerU解析，如果密钥无效或网络问题，会自动切换到本地解析，确保文档能够正常处理。"
              type="info"
              showIcon
              style={{ marginTop: 8 }}
            />
          )}
          {parserMode === 'mineru' && (
            <>
              {/* MinerU配置正常提示 */}
              {mineruConfigStatus && mineruConfigStatus.has_config && mineruConfigStatus.api_status === 'valid' && (
                <Alert
                  message="MinerU API密钥配置正常"
                  description={
                    <div>
                      <div style={{ marginBottom: 8 }}>
                        MinerU API密钥配置正确，可以正常使用文档解析功能。
                      </div>
                    </div>
                  }
                  type="success"
                  action={
                    <Button 
                      size="small"
                      onClick={() => {
                        console.log('手动重新检查MinerU配置');
                        checkMineruConfig();
                      }}
                      loading={checkingMineruConfig}
                    >
                      重新检查
                    </Button>
                  }
                  showIcon
                  style={{ marginTop: 8 }}
                />
              )}
              {/* MinerU配置问题提示 */}
              {mineruConfigStatus && (!mineruConfigStatus.has_config || mineruConfigStatus.api_status !== 'valid') && (
                <Alert
                  message="MinerU配置问题"
                  description={
                    <div>
                      <div style={{ marginBottom: 8 }}>
                        {mineruConfigStatus.error_message?.includes('密钥为空') 
                          ? "MinerU API密钥为空，请重新配置" 
                          : mineruConfigStatus.error_message || "当前MinerU密钥无效或未配置"}
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        选择此模式可能导致解析失败，建议选择自动模式或本地解析。
                      </div>
                      <Space>
                        <Button 
                          type="primary" 
                          size="small"
                          onClick={() => navigate('/user/settings?tab=mineru')}
                        >
                          {mineruConfigStatus.error_message?.includes('密钥为空') ? '重新配置MinerU密钥' : '配置MinerU密钥'}
                        </Button>
                        <Button 
                          size="small"
                          onClick={() => {
                            console.log('手动重新检查MinerU配置');
                            checkMineruConfig();
                          }}
                          loading={checkingMineruConfig}
                        >
                          重新检查
                        </Button>
                      </Space>
                    </div>
                  }
                  type="warning"
                  showIcon
                  style={{ marginTop: 8 }}
                />
              )}
              {/* MinerU配置状态未知提示 */}
              {mineruConfigStatus && mineruConfigStatus.api_status === 'unknown' && (
                <Alert
                  message="MinerU API密钥配置状态未知"
                  description="需要登录后才能检查MinerU API密钥配置状态。登录后可以配置MinerU API密钥以获得更好的文档解析效果。"
                  type="info"
                  action={
                    <Button 
                      type="primary" 
                      size="small"
                      onClick={() => navigate('/login')}
                    >
                      去登录
                    </Button>
                  }
                  showIcon
                  style={{ marginTop: 8 }}
                />
              )}
            </>
          )}
          {parserMode === 'local' && (
            <Alert
              message="本地解析说明"
              description="本地解析支持PDF、Word、Excel、PPT等格式，但解析质量可能不如MinerU。对于复杂文档建议使用MinerU。如果遇到解析失败，请检查是否安装了相应的依赖库。"
              type="info"
              showIcon
              style={{ marginTop: 8 }}
            />
          )}
        </Card>
        
        <Upload.Dragger
          multiple
          fileList={fileList}
          onChange={handleFileUpload}
          beforeUpload={() => false}
          accept=".txt,.pdf,.docx,.doc,.md,.html"
        >
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 TXT, MD, PDF, DOCX, DOC 格式文件，建议文件大小不超过10MB
          </p>
          <p className="ant-upload-hint">
            系统会自动将 PDF、Word 等文档转换为 Markdown 格式进行处理
          </p>
        </Upload.Dragger>
        {/* 解析状态提示 */}
        {parsingStatus === 'loading' && (
          <div style={{ marginTop: 16 }}>
            <Spin /> 正在解析文件，请稍候...
          </div>
        )}
        {parsingStatus === 'success' && (
          <Alert
            type="success"
            message={parserMode === 'local' ? "文件解析完成！点击下方'下一步'继续" : "文件解析完成！可点击下方'处理文件'进行预览和切片"}
            showIcon
            style={{ marginTop: 16, marginBottom: 8 }}
          />
        )}
        {parsingStatus === 'success' && parsedFiles.length > 0 && (
          <div style={{ marginTop: 8 }}>
            {parsedFiles.map(file => (
              <div key={file.filename} style={{ marginBottom: 8, padding: 8, border: '1px solid #eee', borderRadius: 4 }}>
                <b>{file.filename}</b> - 状态: {file.success
                  ? <span style={{ color: '#52c41a', fontWeight: 500 }}>解析成功</span>
                  : <span style={{ color: '#ff4d4f', fontWeight: 500 }}>解析失败</span>}
                {file.error_msg && <div style={{ color: '#ff4d4f' }}>错误: {file.error_msg}</div>}
              </div>
            ))}
          </div>
        )}
        {parsingStatus === 'error' && mineruError && (
          <MinerUErrorAlert 
            error={mineruError} 
            onRetry={() => {
              setParsingStatus('idle');
              setMineruError(null);
              setParsingError('');
            }}
            style={{ marginTop: 16 }}
          />
        )}
        {parsingStatus === 'error' && !mineruError && (
          <Alert type="error" message={`文件解析失败: ${parsingError}`} showIcon style={{ marginTop: 16 }} />
        )}
        <div className={styles.actionBar}>
          <Button
            type="primary"
            onClick={handleProcessFiles}
            disabled={parsedFiles.filter(f => f.success).length === 0 || isProcessing || isCheckingConfig || !isConfigured}
            loading={isProcessing}
          >
            {isProcessing ? '处理中...' : (parserMode === 'local' ? '下一步' : '处理文件')}
          </Button>
          {/* 仅当本地有已解析文件且非本地解析模式时显示清理缓存按钮及备注 */}
          {parsedFiles.length > 0 && parserMode !== 'local' && (
            <>
              <Button
                danger
                style={{ marginLeft: 16 }}
                onClick={handleClearMineruCache}
              >
                清理缓存
              </Button>
              <span style={{ marginLeft: 8, color: '#888', fontSize: 13 }}>
                （清除已经解析的文档）
              </span>
              <Modal
                open={clearCacheModalVisible}
                onCancel={() => setClearCacheModalVisible(false)}
                onOk={doClearMineruCache}
                okText="确定"
                cancelText="取消"
                title="确认清理缓存"
              >
                <div style={{ color: '#ff4d4f', fontWeight: 500 }}>
                  确定要清除所有已解析的文档吗？此操作不可恢复。
                </div>
              </Modal>
            </>
          )}
        </div>
        {/* 预览弹窗 */}
        <Modal
          title="解析结果预览"
          open={previewModalVisible}
          onCancel={() => setPreviewModalVisible(false)}
          footer={[
            <Button key="next" type="primary" disabled={!selectedPreviewFile} onClick={handleNextStep}>
              下一步
            </Button>
          ]}
          width={900}
        >
        {/* 文件列表单选+预览 */}
        <div style={{ maxHeight: 500, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0 }}>
            <thead>
              <tr>
                <th style={{ width: 40 }}></th>
                <th>文件名</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {parsedFiles
                .filter(file => file.success && Array.isArray(file.extracted_files) && file.extracted_files.length > 0)
                .flatMap(file => file.extracted_files.map((fpath: string) => ({
                  file,
                  fpath
                })))
                .map(({ file, fpath }, idx) => (
                  <tr
                    key={fpath}
                    style={{
                      background: selectedPreviewFile && selectedPreviewFile.fpath === fpath ? '#e6f7ff' : undefined,
                      height: 48,
                      verticalAlign: 'middle',
                      borderBottom: '1px solid #f0f0f0',
                      cursor: 'pointer',
                    }}
                    onClick={() => setSelectedPreviewFile({ ...file, fpath })}
                  >
                    <td style={{ padding: '8px 12px' }} onClick={e => e.stopPropagation()}>
                      <Radio
                        checked={selectedPreviewFile && selectedPreviewFile.fpath === fpath}
                        onChange={() => setSelectedPreviewFile({ ...file, fpath })}
                      />
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: 16 }}>{fpath.split('/').pop()}</td>
                    <td style={{ padding: '8px 12px' }}>
                      <Button size="small" style={{ marginLeft: 8, marginRight: 8 }} onClick={e => { e.stopPropagation(); handlePreview(fpath); }}>预览</Button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {/* 单文件预览弹窗 */}
        <Modal
          open={filePreviewModalVisible}
          onCancel={() => setFilePreviewModalVisible(false)}
          footer={null}
          width={900}
          bodyStyle={{ padding: 0 }}
        >
          {renderFilePreviewModal()}
        </Modal>
        </Modal>
      </div>
    </Card>
  );

  const renderChunksContent = () => (
    <Card title="文本分块" className={styles.card}
      extra={
        <Button
          onClick={() => setCurrentTab('upload')}
          style={{ float: 'right' }}
        >
          重新选择文件
        </Button>
      }
    >
      <div className={styles.chunksInfo}>
        <p>
          系统已将文件内容分成了{chunks.length}个文本块，共{chunks.filter(c => c.selected).length}个块被选中用于生成问答对。
          您可以通过下方的复选框选择或取消某些块。
        </p>

        {/* 添加到分块预览页面的分块大小控制 */}
        <div className={styles.chunkSizeSlider}>
          <h4>文本块大小设置 ({chunkSize} 字符)</h4>
          <div className={styles.sliderContainer}>
            <div className={styles.sliderLabel}>较小块 (500)</div>
            <div className={styles.sliderMain}>
              <Slider
                min={500}
                max={3000}
                value={chunkSize}
                onChange={(value) => setChunkSize(value)}
                step={500}
                marks={{
                  500: '500',
                  1000: '1000',
                  2000: '2000',
                  3000: '3000'
                }}
                tooltip={{ formatter: (value) => `${value} 字符` }}
              />
            </div>
            <div className={styles.sliderLabel}>较大块 (3000)</div>
          </div>

          {/* 添加分割策略选择器 */}
          <div className={styles.splitterSelector}>
            <h4>分割策略</h4>
            {/* 主策略按钮组，单独一行并用橙色突出 */}
            <Space style={{ marginBottom: 20 }}>
              <Button
                className={styles.orangePrimary}
                style={{
                  background: splitMode === 'langchain' ? '#fa8c16' : undefined,
                  color: splitMode === 'langchain' ? '#fff' : undefined,
                  borderColor: '#fa8c16',
                  boxShadow: splitMode === 'langchain' ? '0 0 0 2px rgba(250,140,22,0.2)' : undefined,
                }}
                type={splitMode === 'langchain' ? 'primary' : 'default'}
                onClick={() => setSplitMode('langchain')}
              >
                分割策略(使用LangChain)
              </Button>
              <Button
                className={styles.orangePrimary}
                style={{
                  background: splitMode === 'llamaindex' ? '#fa8c16' : undefined,
                  color: splitMode === 'llamaindex' ? '#fff' : undefined,
                  borderColor: '#fa8c16',
                  boxShadow: splitMode === 'llamaindex' ? '0 0 0 2px rgba(250,140,22,0.2)' : undefined,
                }}
                type={splitMode === 'llamaindex' ? 'primary' : 'default'}
                onClick={() => setSplitMode('llamaindex')}
              >
                分割策略(使用LlamaIndex)
              </Button>
            </Space>
            {/* 子策略选项，单独一行，主次分明 */}
            {splitMode === 'langchain' && (
              <div style={{ marginBottom: 8 }}>
                <Radio.Group
                  value={splitterType}
                  onChange={(e) => setSplitterType(e.target.value)}
                  options={[
                    { label: '递归字符分割 (通用)', value: 'recursive' },
                    { label: '代码分割 (针对程序代码)', value: 'code' },
                    { label: 'Markdown分割', value: 'markdown' },
                    { label: 'HTML分割', value: 'html' },
                  ]}
                  optionType="button"
                  buttonStyle="solid"
                  style={{ marginTop: 8 }}
                />
              </div>
            )}
            {splitMode === 'llamaindex' && (
              <div style={{ marginTop: 8, color: '#888' }}>
                <span>将使用 LlamaIndex 后端分块（需后端支持）</span>
              </div>
            )}
          </div>

          <div className={styles.sliderDescription}>
            <p>
              较小的文本块适合生成简单、聚焦的问题，较大的文本块适合生成复杂、综合性的问题。
              调整块大小和分割策略后点击"重新分块"按钮应用更改。
            </p>
          </div>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={handleRechunk}
            loading={isRechunking}
            style={{ marginTop: '8px' }}
          >
            重新分块
          </Button>
        </div>
      </div>

      <div className={styles.chunksList}>
        {chunks.map(chunk => (
          <Card
            key={chunk.id}
            size="small"
            className={`${styles.chunkCard} ${chunk.selected ? styles.chunkSelected : ''}`}
            onClick={() => showChunkModal(chunk)}
          >
            <div className={styles.chunkHeader}>
              <Checkbox
                checked={chunk.selected}
                onChange={(e) => {
                  e.stopPropagation(); // 防止触发卡片点击事件
                  handleChunkSelectionChange(chunk.id, e.target.checked);
                }}
              />
              <div className={styles.chunkInfo}>
                <span>ID: {chunk.id.substring(0, 6)}...</span>
                <span>{chunk.tokens} 字符</span>
                <span
                  style={{ cursor: 'pointer', color: '#1890ff' }}
                  onClick={(e) => {
                    e.stopPropagation(); // 防止触发卡片点击事件
                    showChunkModal(chunk);
                  }}
                >
                  <FullscreenOutlined /> 查看全文
                </span>
              </div>
            </div>
            <div
              className={`${styles.chunkContent} ${expandedChunks.has(chunk.id) ? styles.chunkContentExpanded : ''}`}
            >
              {chunk.content}
            </div>
            <div
              className={styles.viewMoreBtn}
              onClick={(e) => toggleChunkExpand(chunk.id, e)}
            >
              {expandedChunks.has(chunk.id) ? '收起' : '展开'}
            </div>
          </Card>
        ))}
      </div>

      <Form
        form={form}
        layout="horizontal"
        initialValues={{
          count: 3,
          difficulty: 'medium',
          questionTypes: ['factoid', 'conceptual'],
          maxTokens: 1000
        }}
      >
        <div className={styles.formContainer}>
          <Row gutter={[24, 0]}>
            <Col span={24}>
              <Card className={styles.settingCard} bordered={false}>
                <Form.Item
                  label="选择大模型"
                  required
                >
                  <Select
                    value={selectedModelId}
                    onChange={setSelectedModelId}
                    style={{ width: '100%' }}
                    placeholder="请选择大模型"
                  >
                    {availableModels.map(model => (
                      <Option key={model.id} value={model.id}>
                        {model.name} ({model.modelName})
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </Card>
            </Col>
            <Col xs={24} sm={12} md={8} lg={8}>
              <Card className={styles.settingCard} bordered={false}>
                <Form.Item
                  name="count"
                  label={
                    <span className={styles.labelWithIcon}>
                      每块问题数量
                      <Tooltip title="每块文本生成的问题数量，较高的值可能增加生成时间但能生成更多问题">
                        <QuestionCircleOutlined className={styles.infoIcon} />
                      </Tooltip>
                    </span>
                  }
                  rules={[{ required: true }]}
                >
                  <InputNumber min={1} max={10} style={{ width: '100%' }} />
                </Form.Item>
              </Card>
            </Col>

            <Col xs={24} sm={12} md={8} lg={8}>
              <Card className={styles.settingCard} bordered={false}>
                <Form.Item
                  name="maxTokens"
                  label={
                    <span className={styles.labelWithIcon}>
                      Max Tokens
                      <Tooltip title="大模型最多回答的token数，太小可能导致LLM回答不完整，出现解析错误">
                        <QuestionCircleOutlined className={styles.infoIcon} />
                      </Tooltip>
                    </span>
                  }
                  rules={[{ required: true }]}
                >
                  <InputNumber min={100} max={5000} style={{ width: '100%' }} />
                </Form.Item>
              </Card>
            </Col>

            <Col xs={24} sm={12} md={8} lg={8}>
              <Card className={styles.settingCard} bordered={false}>
                <Form.Item
                  name="concurrency"
                  label={
                    <span className={styles.labelWithIcon}>
                      并发请求数
                      <Tooltip title="同时处理的文本块数量，较高的值可能加快生成速度但会增加API调用的频率">
                        <QuestionCircleOutlined className={styles.infoIcon} />
                      </Tooltip>
                    </span>
                  }
                  rules={[{ required: true }]}
                  initialValue={3}
                >
                  <InputNumber min={1} max={40} style={{ width: '100%' }} />
                </Form.Item>
              </Card>
            </Col>

            <Col span={24}>
              <Card className={styles.settingCard} bordered={false}>
                <Form.Item
                  name="questionTypes"
                  label="问题类型"
                  rules={[{ required: true }]}
                >
                  <Select mode="multiple" placeholder="请选择问题类型" style={{ width: '100%' }}>
                    <Option value="factoid">事实型</Option>
                    <Option value="conceptual">概念型</Option>
                    <Option value="procedural">程序型</Option>
                    <Option value="comparative">比较型</Option>
                  </Select>
                </Form.Item>
              </Card>
            </Col>

            {/* Commented out difficulty selection can be uncommented if needed later */}
            {/* <Col xs={24} sm={12} md={8} lg={8}>
              <Card className={styles.settingCard} bordered={false}>
                <Form.Item
                  name="difficulty"
                  label="问题难度"
                  rules={[{ required: true }]}
                >
                  <Select style={{ width: '100%' }}>
                    <Option value="easy">简单</Option>
                    <Option value="medium">中等</Option>
                    <Option value="hard">困难</Option>
                    <Option value="mixed">混合</Option>
                  </Select>
                </Form.Item>
              </Card>
            </Col> */}
          </Row>
        </div>
      </Form>
      {renderPromptTemplateEditor()}

      <div className={styles.actionBar}>
        <Button onClick={() => setCurrentTab('upload')}>
          返回上传
        </Button>
        <Button
          onClick={previewPrompt}
          icon={<EyeOutlined />}
        >
          预览提示词
        </Button>
        <Button
          type="primary"
          onClick={handleGenerateQA}
          disabled={chunks.filter(c => c.selected).length === 0}
        >
          开始生成
        </Button>
      </div>

      {/* 添加模态窗口显示完整内容 */}
      <Modal
        title="文本块详情"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={[
          <Button key="back" onClick={() => setModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {currentChunk && (
          <>
            <div className={styles.modalHeader}>
              <h3>文本块 ID: {currentChunk.id}</h3>
              <div className={styles.modalInfo}>
                <span>字符数量: {currentChunk.tokens}</span>
                <span>来源文件: {questionGeneratorService.getChunkSourceFile(currentChunk.id) || '未知'}</span>
              </div>
            </div>
            <div className={styles.modalContent}>
              {currentChunk.content}
            </div>
          </>
        )}
      </Modal>
    </Card>
  );

  const renderGenerationContent = () => (
    <Card title="生成问答对" className={styles.card}>
      <div className={styles.progressCard}>
        <div className={styles.progressInfo}>
          <div>
            <div>文本块: {progress.completedChunks} / {progress.totalChunks}</div>
            <Progress
              percent={Math.round((progress.completedChunks / progress.totalChunks) * 100)}
              status={progress.error ? 'exception' : 'active'}
            />
          </div>

          <div>
            <div>问答对: {progress.generatedQAPairs} / {progress.totalQAPairs}</div>
            <Progress
              percent={Math.round((progress.generatedQAPairs / progress.totalQAPairs) * 100)}
              status={progress.error ? 'exception' : 'active'}
            />
          </div>
        </div>

        {progress.currentChunk && (
          <div className={styles.currentChunk}>
            <div>正在处理:</div>
            <div>{progress.currentChunk.content.substring(0, 100)}...</div>
          </div>
        )}

        {progress.error && (
          <Alert
            message="生成中出错（仍在继续生成中...）"
            description={progress.error}
            type="error"
            showIcon
          />
        )}

        <div className={styles.generationPreview}>
          <h3>已生成的问答对 ({generatedQAs.length})</h3>
          {generatedQAs.slice(-5).map(qa => (
            <div key={qa.id} className={styles.qaPreview}>
              <div className={styles.question}>Q: {qa.question}</div>
              <div className={styles.answer}>A: {qa.answer.substring(0, 100)}...</div>
            </div>
          ))}
        </div>

        <div className={styles.actionBar}>
          <Button
            danger
            onClick={handleStopGeneration}
            disabled={progress.isCompleted}
          >
            停止生成
          </Button>
          {progress.isCompleted && (
            <Button
              type="primary"
              onClick={() => setCurrentTab('results')}
            >
              查看结果
            </Button>
          )}
        </div>
      </div>
    </Card>
  );

  // 处理查看原始响应的函数
  const handleViewRawResponse = (record: GeneratedQA) => {
    if (record.rawResponse) {
      setCurrentRawResponse(record.rawResponse);
      setRawResponseModalVisible(true);
    } else {
      message.info('没有可用的原始响应');
    }
  };
  
  // 查看失败记录列表
  const handleViewFailedRecords = () => {
    // 从服务获取失败记录列表
    const records = questionGeneratorService.getFailedRequests();
    setFailedRequests(records);
    setFailedRequestsModalVisible(true);
  };

  // 添加一个状态标记是否已加载失败记录
  const [failedRecordsLoaded, setFailedRecordsLoaded] = useState(false);
  
  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  
  // 在切换到结果页时加载失败记录
  useEffect(() => {
    if (currentTab === 'results' && !failedRecordsLoaded) {
      const records = questionGeneratorService.getFailedRequests();
      setFailedRequests(records);
      setFailedRecordsLoaded(true);
    }
  }, [currentTab, failedRecordsLoaded]);
  
  const renderResultsContent = () => {
    // 计算失败的问答对数量
    const failedQAsCount = failedRequests.length;
    const successQAsCount = generatedQAs.length;
    
    return (
    <Card title="生成结果" className={styles.card}>
      <div className={styles.resultSummary}>
        <div className={styles.statCard}>
          <FileTextOutlined className={styles.statIcon} />
          <div className={styles.statInfo}>
            <div className={styles.statValue}>{chunks.filter(c => c.selected).length}</div>
            <div className={styles.statLabel}>处理的文本块</div>
          </div>
        </div>

        {/* 成功的问答对   */}
        { (
          <div className={styles.statCard} >
            <CheckCircleOutlined className={styles.statIcon} style={{ color: '#52c41a' }} />
            <div className={styles.statInfo}>
              <div className={styles.statValue}>{successQAsCount}</div>
              <div className={styles.statLabel}>
                成功的生成
              </div>
            </div>
          </div>
        )}

        
        { (
          <div className={styles.statCard} onClick={handleViewFailedRecords} style={{ cursor: 'pointer' }}>
            <CloseCircleOutlined className={styles.statIcon} style={{ color: '#ff4d4f' }} />
            <div className={styles.statInfo}>
              <div className={styles.statValue}>{failedQAsCount}</div>
              <div className={styles.statLabel}>失败的文本块</div>
              <div className={styles.viewDetails}>点击查看详情</div>
            </div>
          </div>
        )}

        {/* {progress.error && (
          <div className={styles.statCard}>
            <CloseCircleOutlined className={styles.statIcon} style={{ color: '#ff4d4f' }} />
            <div className={styles.statInfo}>
              <div className={styles.statValue}>错误</div>
              <div className={styles.statLabel}>{progress.error}</div>
            </div>
          </div>
        )} */}
      </div>

{/* TODO 生成后立即保存，目前不能删除所选 */}
      <div className={styles.tableHeader}>
        <div className={styles.tableActions}>
          {selectedQAKeys.length > 0 && (
            <Button
              danger
              icon={<DeleteOutlined />}
              onClick={handleDeleteSelectedQAs}
            >
              删除所选 ({selectedQAKeys.length})
            </Button>
          )}
        </div>
      </div>

      <Divider />

      <div className={styles.tableContainer}>
        <Table
          dataSource={generatedQAs}
          rowKey="id"
          // rowSelection={{
          //   selectedRowKeys: selectedQAKeys,
          //   onChange: handleQASelectChange
          // }}
          pagination={{ 
            current: currentPage,
            pageSize: pageSize,
            showTotal: (total, range) => `共 ${total} 条记录，当前显示 ${range[0]}-${range[1]} 条`,
            onChange: (page, pageSize) => {
              setCurrentPage(page);
              setPageSize(pageSize);
            }
          }}
          scroll={{ x: 1200, y: 400 }}
          rowClassName={(record) => record.status === 'failed' ? styles.failedRow : ''}
        >
          <Column
            title="序号"
            key="index"
            width={80}
            align="center"
            render={(_, __, index) => {
              // 使用React状态中的currentPage和pageSize
              // 计算全局序号
              return (currentPage - 1) * pageSize + index + 1;
            }}
          />

          <Column
            title="状态"
            key="status"
            width={80}
            render={(_, record: GeneratedQA) => (
              <span>
                {record.status === 'failed' ? (
                  <Tooltip title={record.errorReason || '生成失败'}>
                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} /> 失败
                  </Tooltip>
                ) : (
                  <span>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> 成功
                  </span>
                )}
              </span>
            )}
          />
          <Column
            title="问题"
            dataIndex="question"
            key="question"
            width={300}
            ellipsis={{ showTitle: false }}
            render={(text) => (
              <Tooltip placement="topLeft" title={text} overlayStyle={{ maxWidth: '600px' }}>
                <span>{text}</span>
              </Tooltip>
            )}
          />
          <Column
            title="回答"
            dataIndex="answer"
            key="answer"
            width={400}
            ellipsis={{ showTitle: false }}
            render={(text) => (
              <Tooltip placement="topLeft" title={text} overlayStyle={{ maxWidth: '600px' }}>
                <span>{text}</span>
              </Tooltip>
            )}
          />
          <Column
            title="难度"
            dataIndex="difficulty"
            key="difficulty"
            width={100}
            render={(text) => {
              const difficultyMap = {
                'easy': '简单',
                'medium': '中等',
                'hard': '困难'
              };
              return (difficultyMap as any)[text] || text;
            }}
          />
          <Column
            title="类别"
            dataIndex="category"
            key="category"
            width={100}
            render={(text) => {
              const categoryMap = {
                'factoid': '事实型',
                'conceptual': '概念型',
                'procedural': '程序型',
                'comparative': '比较型'
              };
              return (categoryMap as any)[text] || text;
            }}
          />
          <Column title="来源文件" dataIndex="sourceFileName" key="sourceFileName" width={150} ellipsis />
          
        </Table>
      </div>

      <div className={styles.actionBar}>
        <Button onClick={() => setCurrentTab('chunks')}>
          返回设置
        </Button>
        <Button type="primary" onClick={handleFinish}>
          完成
        </Button>
      </div>
    </Card>
    );
  };

  return (
    <div className={styles.content}>
      {currentTab === 'upload' && renderUploadContent()}
      {currentTab === 'chunks' && renderChunksContent()}
      {currentTab === 'generate' && renderGenerationContent()}
      {currentTab === 'results' && renderResultsContent()}

      {/* 添加提示词预览模态窗口 */}
      <Modal
        title="提示词预览"
        open={promptModalVisible}
        onCancel={() => setPromptModalVisible(false)}
        footer={[
          <Button key="back" onClick={() => setPromptModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        <div className={styles.promptPreview}>
          <pre>{promptTemplate}</pre>
        </div>
      </Modal>
      
      {/* 添加查看原始响应模态窗口 */}
      <Modal
        title="大模型原始响应"
        open={rawResponseModalVisible}
        onCancel={() => setRawResponseModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setRawResponseModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        <div className={styles.rawResponsePreview}>
          <pre>{currentRawResponse}</pre>
        </div>
      </Modal>
      
      {/* 添加失败记录列表模态窗口 */}
      <Modal
        title={
          <div className={styles.failedRecordsHeader}>
            <WarningOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
            失败记录详情
            <span className={styles.failedRecordsCount}>
              (共 {failedRequests.length} 条)
            </span>
          </div>
        }
        open={failedRequestsModalVisible}
        onCancel={() => setFailedRequestsModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setFailedRequestsModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={900}
        bodyStyle={{ maxHeight: '70vh', overflow: 'auto' }}
      >
        {failedRequests.length > 0 ? (
          <div className={styles.failedRecordsList}>
            <Collapse accordion>
              {failedRequests.map((record, index) => (
                <Collapse.Panel 
                  key={record.id} 
                  header={
                    <div className={styles.failedRecordHeader}>
                      <Badge status="error" />
                      <span className={styles.failedRecordTitle}>
                        失败记录 #{index + 1}: {record.sourceFileName}
                      </span>
                      <span className={styles.failedRecordError}>
                        {record.errorMessage}
                      </span>
                      <span className={styles.failedRecordTime}>
                        {new Date(record.timestamp).toLocaleString()}
                      </span>
                    </div>
                  }
                >

                  

                  <div className={styles.failedRecordDetail}>
                    {record.chunkContent && (
                      <div >
                        <Typography.Title level={5}>文本块内容</Typography.Title>
                        <div   style={{ marginBottom: '16px', width: '100%', overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word',background: '#f5f5f5', borderRadius: '4px', padding: '8px' }}>
                          <pre>{record.chunkContent.slice(0, 100)} ...</pre>
                        </div>
                      </div>
                    )}

                    {/* <Typography.Title level={5}>请求提示词</Typography.Title>
                    <div className={styles.promptPreview}>
                      <pre>{record.promptText}</pre>
                    </div> */}
                    
                    <Divider />
                    
                    <Typography.Title level={5}>错误信息</Typography.Title>
                    <div className={styles.errorMessage}>
                      <Typography.Text type="danger">
                        {record.errorMessage}
                      </Typography.Text>
                    </div>
                    
                    {record.rawResponse && (
                      <>
                        <Divider />
                        <Typography.Title level={5}>原始响应</Typography.Title>
                        <div className={styles.rawResponsePreview}>
                          <pre>{record.rawResponse}</pre>
                        </div>
                      </>
                    )}
                  </div>
                </Collapse.Panel>
              ))}
            </Collapse>
          </div>
        ) : (
          <Empty 
            description="没有失败记录" 
            image={Empty.PRESENTED_IMAGE_SIMPLE} 
          />
        )}
      </Modal>
    </div>
  );
};

export default QuestionGenerationContent; 