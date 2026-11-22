
import React, { useEffect, useRef, useState } from 'react';

import {
  Box,
  Button,
  Chip,
  Grid,
  IconButton,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
  Alert,
  Divider,
  Tooltip
} from '@mui/material';

import {
  Send,
  Trash2,
  Copy,
  ThumbsUp,
  ThumbsDown
} from 'lucide-react';

import { api, errorText, can } from '../api';

import {
  PageHead,
  Surface,
  Evidence,
  Answer,
  ErrorBox,
  Empty
} from '../components/Common';

// Available AI agents
const AGENTS = [
  { value: 'auto', label: 'Automatic routing' },
  { value: 'rag', label: 'Document RAG' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'fraud', label: 'Fraud & Risk' },
  { value: 'policy', label: 'Policy Comparison' },
  { value: 'report', label: 'Report Generation' }
];

// Suggested questions
const SUGGEST = [
  'What changed in the Credit Risk Policy between versions?',
  'Explain the loan eligibility conditions in plain language.',
  'Prepare a KYC compliance evidence checklist.',
  'Summarize the synthetic phishing investigation report.'
];

export default function Chat({ role }) {

  const [question, setQuestion] = useState('');
  const [agent, setAgent] = useState('auto');
  const [history, setHistory] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');

  const bottom = useRef(null);

  // FIX 1: Load conversation history safely
  useEffect(() => {
    let active = true;

    async function loadHistory() {
      try {
        const response = await api.get('/chat/history');

        if (active) {
          setHistory(
            Array.isArray(response.data)
              ? response.data
              : []
          );
        }
      } catch (err) {
        if (active) {
          console.error(
            'Failed to load conversation history:',
            err
          );
        }
      }
    }

    loadHistory();

    return () => {
      active = false;
    };
  }, []);

  // FIX 2: Scroll without returning an invalid cleanup value
  useEffect(() => {
    if (bottom.current) {
      bottom.current.scrollIntoView({
        behavior: 'smooth',
        block: 'end'
      });
    }
  }, [history.length]);

  // Send question to backend
  async function send(q = question) {

    if (q.trim().length < 3 || working) {
      return;
    }

    setWorking(true);
    setError('');

    try {
      const { data } = await api.post('/chat', {
        message: q,
        agent: agent,
        conversation_id: conversationId
      });

      setConversationId(data.conversation_id);

      setHistory((old) => [
        ...old,
        {
          id: data.message_id,
          question: q,
          answer: data.answer,
          agent: data.agent,
          conversation_id: data.conversation_id,
          created_at: data.created_at,
          citations: data.citations || []
        }
      ]);

      setQuestion('');

    } catch (err) {
      console.error('AI Chat Error:', err);
      setError(errorText(err));

    } finally {
      setWorking(false);
    }
  }

  // Clear conversation history
  async function clear() {

    if (
      !window.confirm(
        'Delete your saved conversation history?'
      )
    ) {
      return;
    }

    try {
      await api.delete('/chat/history');

      setHistory([]);
      setConversationId(null);
      setError('');

    } catch (err) {
      setError(errorText(err));
    }
  }

  // Submit AI feedback
  async function feedback(cid, rating) {

    try {
      await api.post('/feedback', {
        conversation_id: cid,
        rating: rating,
        comment: ''
      });

    } catch (err) {
      setError(errorText(err));
    }
  }

  // Copy AI response
  async function copyResponse(text) {

    try {
      await navigator.clipboard.writeText(text || '');
    } catch (err) {
      console.error('Copy failed:', err);
    }
  }

  return (
    <>
      <PageHead
        title="AI Banking Assistant"
        subtitle="Ask source-grounded questions about indexed banking documents."
        action={
          <Button
            color="inherit"
            variant="outlined"
            startIcon={<Trash2 size={16} />}
            onClick={clear}
          >
            Clear history
          </Button>
        }
      />

      <Grid container spacing={2.5}>

        {/* Main chat area */}
        <Grid item xs={12} lg={8}>

          <Surface
            title="Conversation"
            sx={{ minHeight: 500 }}
          >

            <Box
              sx={{
                height: { xs: 370, md: 500 },
                overflowY: 'auto',
                pr: 0.5
              }}
            >

              {history.length > 0 ? (

                history.map((r, index) => (

                  <Box
                    key={r.id || index}
                    mb={2.6}
                  >

                    {/* User message */}
                    <Box
                      sx={{
                        ml: 'auto',
                        maxWidth: '87%',
                        background: '#e7f0f8',
                        borderRadius: '14px 14px 0 14px',
                        p: 2
                      }}
                    >
                      <Typography fontSize={14}>
                        {r.question}
                      </Typography>
                    </Box>

                    {/* AI answer */}
                    <Box
                      sx={{
                        maxWidth: '96%',
                        border: '1px solid #e5eaf0',
                        borderRadius: '14px 14px 14px 0',
                        mt: 1.3,
                        p: 2.1,
                        background: '#fcfdff'
                      }}
                    >

                      <Chip
                        size="small"
                        label={
                          r.agent?.toUpperCase() || 'RAG'
                        }
                        sx={{ mb: 1.5 }}
                      />

                      {/* AI response */}
                      <Answer text={r.answer || ''} />

                      {/* Source citations */}
                      <Evidence
                        citations={r.citations || []}
                      />

                      <Stack
                        direction="row"
                        justifyContent="space-between"
                        mt={1.5}
                        alignItems="center"
                      >

                        <Typography
                          color="text.secondary"
                          fontSize={11}
                        >
                          {r.created_at
                            ? new Date(
                                r.created_at
                              ).toLocaleString()
                            : ''}
                        </Typography>

                        <Stack direction="row">

                          {/* Copy response */}
                          <Tooltip title="Copy response">
                            <IconButton
                              size="small"
                              onClick={() =>
                                copyResponse(r.answer)
                              }
                            >
                              <Copy size={16} />
                            </IconButton>
                          </Tooltip>

                          {/* Positive feedback */}
                          <Tooltip title="Helpful">
                            <IconButton
                              size="small"
                              onClick={() =>
                                feedback(
                                  r.conversation_id,
                                  5
                                )
                              }
                            >
                              <ThumbsUp size={16} />
                            </IconButton>
                          </Tooltip>

                          {/* Negative feedback */}
                          <Tooltip title="Not helpful">
                            <IconButton
                              size="small"
                              onClick={() =>
                                feedback(
                                  r.conversation_id,
                                  1
                                )
                              }
                            >
                              <ThumbsDown size={16} />
                            </IconButton>
                          </Tooltip>

                        </Stack>

                      </Stack>

                    </Box>

                  </Box>

                ))

              ) : (

                <Empty
                  title="What would you like to investigate?"
                  detail="Load the synthetic dataset first, then ask a policy, compliance or risk question."
                />

              )}

              <div ref={bottom} />

            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Error messages */}
            <ErrorBox error={error} />

            {/* Question input */}
            <Stack
              direction={{
                xs: 'column',
                sm: 'row'
              }}
              spacing={1}
            >

              <TextField
                multiline
                minRows={2}
                maxRows={4}
                placeholder="Ask a question about the uploaded banking documents..."
                fullWidth
                value={question}
                disabled={working}
                onChange={(e) =>
                  setQuestion(e.target.value)
                }
                onKeyDown={(e) => {
                  if (
                    e.key === 'Enter' &&
                    !e.shiftKey
                  ) {
                    e.preventDefault();
                    send();
                  }
                }}
              />

              <Button
                variant="contained"
                onClick={() => send()}
                disabled={
                  working ||
                  question.trim().length < 3
                }
                endIcon={<Send size={16} />}
                sx={{ minWidth: 115 }}
              >
                {working
                  ? 'Thinking...'
                  : 'Ask AI'}
              </Button>

            </Stack>

            <Typography
              fontSize={11}
              color="text.secondary"
              mt={1}
            >
              Shift+Enter for a new line.
              Source citations are extracted from
              the document index, not invented
              by the model.
            </Typography>

          </Surface>

        </Grid>

        {/* Right sidebar */}
        <Grid item xs={12} lg={4}>

          {/* Agent selection */}
          <Surface
            title="Agent selection"
            subtitle="Agent workflows have different prompts and output requirements."
          >

            <Select
              fullWidth
              size="small"
              value={agent}
              disabled={working}
              onChange={(e) =>
                setAgent(e.target.value)
              }
            >

              {AGENTS.filter(
                (a) =>
                  a.value === 'auto' ||
                  ['rag', 'policy', 'report'].includes(
                    a.value
                  ) ||
                  can(role, a.value)
              ).map((a) => (

                <MenuItem
                  key={a.value}
                  value={a.value}
                >
                  {a.label}
                </MenuItem>

              ))}

            </Select>

            <Typography
              variant="body2"
              color="text.secondary"
              mt={2}
            >
              The automatic router chooses a
              specialized agent from your question.
              Permissions are checked by the backend.
            </Typography>

          </Surface>

          {/* Suggested questions */}
          <Box mt={2}>

            <Surface title="Try a question">

              <Stack spacing={1.3}>

                {SUGGEST.map((s) => (

                  <Button
                    key={s}
                    size="small"
                    variant="outlined"
                    disabled={working}
                    sx={{
                      textAlign: 'left',
                      justifyContent: 'flex-start',
                      whiteSpace: 'normal',
                      py: 1.5
                    }}
                    onClick={() => setQuestion(s)}
                  >
                    {s}
                  </Button>

                ))}

              </Stack>

            </Surface>

          </Box>

          {/* Safety notice */}
          <Alert
            severity="warning"
            sx={{ mt: 2 }}
          >
            AI output is informational and must
            be reviewed by qualified staff.
            This demo uses fictional policies only.
          </Alert>

        </Grid>

      </Grid>
    </>
  );
}