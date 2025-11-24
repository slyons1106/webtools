import React, { useState } from 'react';
import { Container, Button, Form } from 'react-bootstrap';

export function ToolsPage() {
  const [output, setOutput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleModemFailedCount = async () => {
    setIsLoading(true);
    setOutput('');
    try {
      const response = await fetch('/api/tools/modem-failed-count');
      const data = await response.json();
      setOutput(data.output);
    } catch (error) {
      setOutput('Error fetching data.');
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
      <Form.Group controlId="output">
        <Form.Label>Output</Form.Label>
        <Form.Control
          as="textarea"
          rows={15}
          value={output}
          readOnly
          placeholder="Results will be shown here..."
          style={{ whiteSpace: 'pre-wrap' }}
        />
      </Form.Group>
    </Container>
  );
}
