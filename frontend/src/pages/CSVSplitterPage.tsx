import React, { useState } from 'react';
import axios from 'axios';
import {
  Container,
  Form,
  Button,
  Spinner,
  Alert,
  Row,
  Col,
} from 'react-bootstrap';

const API_BASE_URL = 'http://localhost:8000';

export function CSVSplitterPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [rowsPerChunk, setRowsPerChunk] = useState<number>(100000); // Default from original script
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
      setDownloadUrl(null); // Reset download URL on new file selection
      setError(null);
    }
  };

  const handleRowsPerChunkChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(event.target.value, 10);
    if (!isNaN(value) && value > 0) {
      setRowsPerChunk(value);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedFile) {
      setError('Please select a CSV file to split.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setDownloadUrl(null);
    setFileName(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    // rows_per_chunk should be a query parameter, not part of formData

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/csvsplitter/split?rows_per_chunk=${rowsPerChunk}`,
        formData,
        {
        responseType: 'blob', // Important: responseType must be 'blob' for file downloads
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      // Create a URL for the blob and trigger download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const contentDisposition = response.headers['content-disposition'];
      let downloadedFileName = 'split_chunks.zip'; // Default filename
      if (contentDisposition) {
        const fileNameMatch = contentDisposition.match(/filename="([^"]+)"/);
        if (fileNameMatch && fileNameMatch[1]) {
          downloadedFileName = fileNameMatch[1];
        }
      }
      setFileName(downloadedFileName);
      setDownloadUrl(url);

    } catch (err: any) {
      if (axios.isAxiosError(err) && err.response) {
        // Try to parse error message from blob if available
        try {
          const errorBlob = new Blob([err.response.data], { type: 'application/json' });
          const reader = new FileReader();
          reader.onload = (e) => {
            if (e.target && typeof e.target.result === 'string') {
              const errorData = JSON.parse(e.target.result);
              setError(`Splitting failed: ${errorData.detail || err.message}`);
            } else {
              setError(`Splitting failed: ${err.response.statusText || err.message}`);
            }
          };
          reader.readAsText(errorBlob);
        } catch (parseError) {
          setError(`Splitting failed: ${err.response.statusText || err.message}`);
        }
      } else {
        setError('An unexpected error occurred. Is the backend server running?');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container className="mt-4">
      <h1>CSV Splitter & Zipper</h1>
      <Form onSubmit={handleSubmit} className="mt-4 p-3 border rounded">
        <Row className="mb-3">
          <Form.Group as={Col} controlId="formFile">
            <Form.Label>Upload CSV File</Form.Label>
            <Form.Control type="file" accept=".csv" onChange={handleFileChange} required />
          </Form.Group>
        </Row>
        <Row className="mb-3">
          <Form.Group as={Col} controlId="formRowsPerChunk">
            <Form.Label>Rows per Chunk</Form.Label>
            <Form.Control
              type="number"
              value={rowsPerChunk}
              onChange={handleRowsPerChunkChange}
              min="1"
              required
            />
            <Form.Text className="text-muted">
              Number of rows each output CSV file should contain.
            </Form.Text>
          </Form.Group>
        </Row>
        <Button variant="primary" type="submit" disabled={isLoading || !selectedFile}>
          {isLoading ? (
            <>
              <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" />
              <span className="ms-2">Splitting...</span>
            </>
          ) : (
            'Split & Zip File'
          )}
        </Button>
      </Form>

      {error && <Alert variant="danger" className="mt-3">{error}</Alert>}

      {downloadUrl && fileName && (
        <Alert variant="success" className="mt-3">
          CSV splitting complete!{' '}
          <Alert.Link href={downloadUrl} download={fileName}>
            Click here to download "{fileName}"
          </Alert.Link>
        </Alert>
      )}
    </Container>
  );
}
