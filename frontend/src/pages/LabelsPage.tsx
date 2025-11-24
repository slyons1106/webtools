import React, { useState, useEffect } from 'react';
import { Container, Button, Form, Row, Col } from 'react-bootstrap';

export function LabelsPage() {
  const [todayOutput, setTodayOutput] = useState('');
  const [tomorrowOutput, setTomorrowOutput] = useState('');
  const [isTodayLoading, setIsTodayLoading] = useState(false);
  const [isTomorrowLoading, setIsTomorrowLoading] = useState(false);

  const fetchTodayData = async () => {
    setIsTodayLoading(true);
    setTodayOutput('');
    try {
      const response = await fetch('/api/labels/today');
      const data = await response.json();
      setTodayOutput(data.output);
    } catch (error) {
      setTodayOutput('Error fetching today\'s data.');
      console.error('Error fetching today\'s data:', error);
    } finally {
      setIsTodayLoading(false);
    }
  };

  const fetchTomorrowData = async () => {
    setIsTomorrowLoading(true);
    setTomorrowOutput('');
    try {
      const response = await fetch('/api/labels/tomorrow');
      const data = await response.json();
      setTomorrowOutput(data.output);
    } catch (error) {
      setTomorrowOutput('Error fetching tomorrow\'s data.');
      console.error('Error fetching tomorrow\'s data:', error);
    } finally {
      setIsTomorrowLoading(false);
    }
  };

  useEffect(() => {
    fetchTodayData();
  }, []);

  return (
    <Container className="mt-4">
      <h1>Labels</h1>
      <hr />
      <Row>
        <Col md={6}>
          <h2>Today's Labels</h2>
          <Form.Group controlId="today-output">
            <Form.Control
              as="textarea"
              rows={20}
              value={isTodayLoading ? 'Loading...' : todayOutput}
              readOnly
              placeholder="Today's results will be shown here..."
              style={{ whiteSpace: 'pre-wrap' }}
            />
          </Form.Group>
        </Col>
        <Col md={6}>
          <h2>Tomorrow's Labels</h2>
          <Button
            variant="primary"
            onClick={fetchTomorrowData}
            disabled={isTomorrowLoading}
            className="mb-3"
          >
            {isTomorrowLoading ? 'Loading...' : 'Refresh Tomorrow'}
          </Button>
          <Form.Group controlId="tomorrow-output">
            <Form.Control
              as="textarea"
              rows={20}
              value={isTomorrowLoading ? 'Loading...' : tomorrowOutput}
              readOnly
              placeholder="Tomorrow's results will be shown here..."
              style={{ whiteSpace: 'pre-wrap' }}
            />
          </Form.Group>
        </Col>
      </Row>
    </Container>
  );
}
