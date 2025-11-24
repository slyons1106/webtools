import React, { useState } from 'react';
import axios from 'axios';
import {
  Container,
  Row,
  Col,
  Form,
  Button,
  ListGroup,
  Spinner,
  Alert,
  Image,
  Breadcrumb,
  Card,
} from 'react-bootstrap';

const API_BASE_URL = 'http://localhost:8000';

interface S3Item {
  name: string;
  type: 'folder' | 'file';
  key: string;
}

interface S3Object {
  key: string;
  content: string; // base64 data URL
  size: number;
  last_modified: string;
}

export function S3ViewerPage() {
  // State
  const [bucket, setBucket] = useState<string>('pat-labels');
  const [prefix, setPrefix] = useState<string>('');
  const [items, setItems] = useState<S3Item[]>([]);
  const [selectedImage, setSelectedImage] = useState<S3Object | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch S3 items when connection details change
  const fetchItems = async (newPrefix: string) => {
    if (!bucket) {
      setError('Bucket must be specified.');
      return;
    }
    setIsLoading(true);
    setError(null);
    setSelectedImage(null);
    try {
      const response = await axios.get<S3Item[]>(`${API_BASE_URL}/api/s3/list`, {
        params: { bucket, prefix: newPrefix },
      });
      setItems(response.data);
      setPrefix(newPrefix);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to list S3 items.');
      setItems([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleItemClick = (item: S3Item) => {
    if (item.type === 'folder') {
      fetchItems(item.key);
    } else {
      if (item.key.toLowerCase().endsWith('.png')) {
        fetchObject(item.key);
      }
    }
  };

  const fetchObject = async (key: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await axios.get<S3Object>(`${API_BASE_URL}/api/s3/object`, {
        params: { bucket, key },
      });
      setSelectedImage(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch S3 object.');
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleBreadcrumbClick = (index: number) => {
    const pathParts = prefix.split('/').filter(p => p);
    const newPrefix = pathParts.slice(0, index).join('/') + '/';
    fetchItems(index === 0 ? '' : newPrefix);
  };

  const handleSaveImage = () => {
    if (!selectedImage) return;
    const link = document.createElement('a');
    link.href = selectedImage.content;
    link.download = selectedImage.key.split('/').pop() || 'image.png';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Container className="mt-4">
      <h1>S3 Label Viewer</h1>
      <Card className="mt-4">
        <Card.Header>
          <h5>S3 Bucket Connection</h5>
        </Card.Header>
        <Card.Body>
          <Form>
            <Row>
              <Form.Group as={Col} md="6" controlId="formBucket">
                <Form.Label>S3 Bucket</Form.Label>
                <Form.Control type="text" value={bucket} onChange={(e) => setBucket(e.target.value)} />
              </Form.Group>
              <Form.Group as={Col} md="6" className="d-flex align-items-end">
                <Button onClick={() => fetchItems('')} disabled={isLoading}>Connect</Button>
              </Form.Group>
            </Row>
          </Form>
        </Card.Body>
      </Card>

      {error && <Alert variant="danger" className="mt-3">{error}</Alert>}

      <Row className="mt-4">
        <Col md={5}>
          <Card>
            <Card.Header>
              <h4>Bucket Browser</h4>
            </Card.Header>
            <Card.Body>
              <Breadcrumb>
                <Breadcrumb.Item onClick={() => handleBreadcrumbClick(0)} active={prefix === ''}>{bucket}</Breadcrumb.Item>
                {prefix.split('/').filter((p: string) => p).map((part: string, i: number) => (
                  <Breadcrumb.Item key={i} onClick={() => handleBreadcrumbClick(i + 1)} active={i === prefix.split('/').filter(p => p).length - 1}>
                    {part}
                  </Breadcrumb.Item>
                ))}
              </Breadcrumb>
              <ListGroup>
                {isLoading && <div className="text-center"><Spinner animation="border" /></div>}
                {!isLoading && items.map(item => (
                  <ListGroup.Item key={item.key} action onClick={() => handleItemClick(item)} style={{ cursor: 'pointer' }}>
                    <i className={`bi ${item.type === 'folder' ? 'bi-folder' : 'bi-file-earmark'} me-2`}></i>
                    {item.name}
                  </ListGroup.Item>
                ))}
              </ListGroup>
            </Card.Body>
          </Card>
        </Col>
        <Col md={7}>
          <Card>
            <Card.Header>
              <h4>Image Preview</h4>
            </Card.Header>
            <Card.Body>
              <div className="text-center" style={{ minHeight: '400px' }}>
                {selectedImage ? (
                  <>
                    <Image src={selectedImage.content} fluid thumbnail />
                    <div className="mt-2 text-muted small">{selectedImage.key}</div>
                    <Button variant="success" size="sm" className="mt-2" onClick={handleSaveImage}>Save Image</Button>
                  </>
                ) : (
                  <div className="d-flex align-items-center justify-content-center h-100">
                    Select a PNG file to view
                  </div>
                )}
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
}
