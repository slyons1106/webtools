import React, { useState } from 'react';
import { Container, Button, Form } from 'react-bootstrap';

export function ToolsPage() {
  const [output, setOutput] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');

  const handleModemFailedCount = async () => {
    setIsLoading(true);
    setOutput(null);
    setMessage('Querying DynamoDB table...');
    try {
      const response = await fetch('/api/tools/modem-failed-count');
      const data = await response.json();
      setOutput(data);
      setMessage(data.message || (data.error ? `Error: ${data.error}` : ''));
    } catch (error) {
      setMessage('Error fetching data.');
      console.error('Error fetching modem failed count:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container className="mt-4">
      <h1>Tools</h1>
      <hr />
      <div className="mb-3">
        <Button
          variant="primary"
          onClick={handleModemFailedCount}
          disabled={isLoading}
        >
          {isLoading ? 'Loading...' : 'Modem Failed Count'}
        </Button>
      </div>
      {message && <p>{message}</p>}
      <Form.Group controlId="output">
        <Form.Label>Output</Form.Label>
        <Form.Control
          as="textarea"
          rows={20}
          value={output ? JSON.stringify(output, null, 2) : ''}
          readOnly
          placeholder="Results will be shown here..."
          style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}
        />
      </Form.Group>
    </Container>
  );
}
