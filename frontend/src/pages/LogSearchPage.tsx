import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Container,
  Form,
  Button,
  Table,
  Spinner,
  Alert,
  Row,
  Col,
} from 'react-bootstrap';

const API_BASE_URL = 'http://localhost:8000';

interface LogResult {
  timestamp: string;
  message: string;
  logStream: string;
  log: string;
}

export function LogSearchPage() {
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<string>('');
  const [handlers, setHandlers] = useState<string[]>([]);
  const [selectedHandler, setSelectedHandler] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [startTime, setStartTime] = useState<string>('');
  const [endTime, setEndTime] = useState<string>('');
  const [results, setResults] = useState<LogResult[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isHandlerLoading, setIsHandlerLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProfiles = async () => {
      try {
        const response = await axios.get<string[]>(`${API_BASE_URL}/api/aws-profiles`);
        setProfiles(response.data);
        if (response.data.length > 0) {
          setSelectedProfile(response.data[0]);
        }
      } catch (err) {
        setError('Failed to fetch AWS profiles. Make sure the backend server is running.');
      }
    };

    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    setEndTime(now.toISOString().slice(0, 16));
    setStartTime(oneHourAgo.toISOString().slice(0, 16));

    fetchProfiles();
  }, []);

  useEffect(() => {
    if (!selectedProfile) return;

    const fetchHandlers = async () => {
      setIsHandlerLoading(true);
      setHandlers([]);
      setSelectedHandler('');
      try {
        const response = await axios.get<string[]>(`${API_BASE_URL}/api/handlers`, {
          params: { profile: selectedProfile },
        });
        setHandlers(response.data);
        if (response.data.length > 0) {
          setSelectedHandler(response.data[0]);
        }
      } catch (err) {
        setError('Failed to fetch handlers.');
      } finally {
        setIsHandlerLoading(false);
      }
    };

    fetchHandlers();
  }, [selectedProfile]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResults([]);

    try {
      const response = await axios.post<LogResult[]>(`${API_BASE_URL}/api/search`, {
        profile: selectedProfile,
        handler: selectedHandler,
        search_term: searchTerm,
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
      });
      setResults(response.data);
    } catch (err: any) {
      if (axios.isAxiosError(err) && err.response) {
        setError(`Search failed: ${err.response.data.detail || err.message}`);
      } else {
        setError('An unexpected error occurred. Is the backend server running?');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (text: string, e: React.MouseEvent<HTMLButtonElement>) => {
    navigator.clipboard.writeText(text);
    const button = e.currentTarget;
    const originalText = button.innerText;
    button.innerText = 'Copied!';
    button.disabled = true;
    setTimeout(() => {
      button.innerText = originalText;
      button.disabled = false;
    }, 1500);
  };

  return (
    <Container className="mt-4">
      <h1>CloudWatch Log Search</h1>
      <Form onSubmit={handleSearch} className="mt-4">
        <Row className="mb-3">
          <Form.Group as={Col} controlId="formProfile">
            <Form.Label>AWS Profile</Form.Label>
            <Form.Select
              value={selectedProfile}
              onChange={(e) => setSelectedProfile(e.target.value)}
              disabled={profiles.length === 0}
            >
              {profiles.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Form.Select>
          </Form.Group>
          <Form.Group as={Col} controlId="formHandler">
            <Form.Label>API Handler</Form.Label>
            <Form.Select
              value={selectedHandler}
              onChange={(e) => setSelectedHandler(e.target.value)}
              disabled={isHandlerLoading || handlers.length === 0}
            >
              {isHandlerLoading ? (
                <option>Loading handlers...</option>
              ) : (
                handlers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))
              )}
            </Form.Select>
          </Form.Group>
        </Row>
        <Row className="mb-3">
          <Form.Group as={Col} controlId="formSearchTerm">
            <Form.Label>Search Term (e.g., Policy Number)</Form.Label>
            <Form.Control
              type="text"
              placeholder="Enter search term"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              required
            />
          </Form.Group>
        </Row>
        <Row className="mb-3">
          <Form.Group as={Col} controlId="formStartTime">
            <Form.Label>Start Time</Form.Label>
            <Form.Control
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              required
            />
          </Form.Group>
          <Form.Group as={Col} controlId="formEndTime">
            <Form.Label>End Time</Form.Label>
            <Form.Control
              type="datetime-local"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              required
            />
          </Form.Group>
        </Row>
        <Button variant="primary" type="submit" disabled={isLoading || isHandlerLoading}>
          {isLoading ? (
            <>
              <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" />
              <span className="ms-2">Searching...</span>
            </>
          ) : (
            'Search'
          )}
        </Button>
      </Form>

      <hr className="my-4" />

      {error && <Alert variant="danger">{error}</Alert>}

      <h2>Results</h2>
      <Table striped bordered hover responsive>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Message</th>
            <th>Log Stream</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr>
              <td colSpan={4} className="text-center">
                <Spinner animation="border" />
              </td>
            </tr>
          )}
          {!isLoading && results.length === 0 && (
            <tr>
              <td colSpan={4} className="text-center">
                No results found.
              </td>
            </tr>
          )}
          {results.map((res, index) => (
            <tr key={index}>
              <td>{new Date(res.timestamp).toLocaleString()}</td>
              <td>
                <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{res.message}</pre>
              </td>
              <td>{res.logStream}</td>
              <td>
                <Button variant="outline-secondary" size="sm" onClick={(e) => handleCopy(res.message, e)}>
                  Copy
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Container>
  );
}
