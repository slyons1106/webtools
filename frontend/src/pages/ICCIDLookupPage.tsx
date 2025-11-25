import React, { useState, useEffect } from 'react';
import { Container, Form, Button, Spinner, Alert, Card, Table, ListGroup, Row, Col } from 'react-bootstrap';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000'; // Assuming backend runs on this

export function ICCIDLookupPage() {
  const [iccid, setIccid] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null); // To store the JSON response
  const [editableShadow, setEditableShadow] = useState<{[key: string]: any}>({}); // State for editable shadow fields
  const [isUpdatingShadow, setIsUpdatingShadow] = useState(false); // State for shadow update loading
  const [updateMessage, setUpdateMessage] = useState<string | null>(null); // State for update success/error messages

  // Effect to initialize editableShadow when results are loaded
  useEffect(() => {
    if (results && results.iot && results.iot.shadow) {
      const shadow = results.iot.shadow;
      // Initialize with current shadow values, or default if not present
      setEditableShadow({
        'Debug': shadow['Debug'] !== undefined ? Boolean(shadow['Debug']) : false, // Initialize as boolean
        'Trip-Timeout': shadow['Trip-Timeout'] !== undefined ? shadow['Trip-Timeout'] : '',
        'After-Trip-Reports': shadow['After-Trip-Reports'] !== undefined ? Boolean(shadow['After-Trip-Reports']) : false, // Initialize as boolean
        'Heartbeat-Interval': shadow['Heartbeat-Interval'] !== undefined ? shadow['Heartbeat-Interval'] : '',
      });
    } else {
      setEditableShadow({}); // Clear editable shadow if no results or shadow
    }
  }, [results]); // Re-run when results change

  const handleLookup = async () => {
    if (!iccid) {
      setError('Please enter an ICCID.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setResults(null);
    setUpdateMessage(null); // Clear update message on new lookup

    try {
      const response = await axios.get(`${API_BASE_URL}/api/device_lookup`, {
        params: { iccid: iccid }
      });
      setResults(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to perform ICCID lookup.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChangeShadowField = (key: string, value: any) => {
    setEditableShadow(prev => ({ ...prev, [key]: value }));
  };

  const handleUpdateShadow = async () => {
    if (!iccid) {
      setError('ICCID is required to update shadow.');
      return;
    }
    
    setIsUpdatingShadow(true);
    setError(null);
    setUpdateMessage(null);

    const desiredStatePayload: {[key: string]: any} = {};
    // These are the DISPLAY keys used in the frontend `editableShadow` state
    const editableDisplayKeys = ['Debug', 'Trip-Timeout', 'After-Trip-Reports', 'Heartbeat-Interval'];
    
    // Map display keys back to internal keys for the backend payload
    const backendKeyMap: {[key: string]: string} = {
      'Debug': 'debug',
      'Trip-Timeout': 'trip-timeout',
      'After-Trip-Reports': 'after-trip-reports',
      'Heartbeat-Interval': 'heartbeat-interval',
    };

    editableDisplayKeys.forEach(displayKey => {
        const backendKey = backendKeyMap[displayKey];
        if (editableShadow[displayKey] !== undefined && editableShadow[displayKey] !== '') {
            if (displayKey === 'Debug') {
                desiredStatePayload[backendKey] = Boolean(editableShadow[displayKey]); // Convert to boolean
            } else if (displayKey === 'After-Trip-Reports') {
                desiredStatePayload[backendKey] = Boolean(editableShadow[displayKey]); // Convert to boolean
            }
            else {
                desiredStatePayload[backendKey] = parseInt(editableShadow[displayKey]); // Assuming others are integers
            }
        }
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/api/update_shadow`, {
        iccid: iccid,
        desired_state: desiredStatePayload
      });
      setUpdateMessage(response.data?.message || 'Shadow updated successfully!');
      // Re-fetch data to show updated shadow state
      await handleLookup();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update shadow.');
    } finally {
      setIsUpdatingShadow(false);
    }
  };

  return (
    <Container className="mt-4">
      <h1>ICCID Lookup</h1>
      <Card className="mb-4">
        <Card.Body>
          <Form>
            <Form.Group className="mb-3" controlId="formIccid">
              <Form.Label>ICCID</Form.Label>
              <Form.Control
                type="text"
                placeholder="Enter ICCID"
                value={iccid}
                onChange={(e) => setIccid(e.target.value)}
                disabled={isLoading}
              />
            </Form.Group>
            <Button variant="primary" onClick={handleLookup} disabled={isLoading}>
              {isLoading ? <Spinner animation="border" size="sm" className="me-2" /> : null}
              Lookup
            </Button>
          </Form>
        </Card.Body>
      </Card>

      {error && <Alert variant="danger">{error}</Alert>}
      {updateMessage && <Alert variant="success">{updateMessage}</Alert>}

      {results && (
        <Card className="mt-4">
          <Card.Header>
            <h2>Lookup Results for {results.general?.iccid || 'N/A'}</h2>
          </Card.Header>
          <Card.Body>
            {results.errors && results.errors.length > 0 && (
              <Alert variant="warning" className="mb-3">
                <h4>Warnings/Errors during Lookup:</h4>
                <ul>
                  {results.errors.map((err: string, index: number) => (
                    <li key={index}>{err}</li>
                  ))}
                </ul>
              </Alert>
            )}
            
            <Row>
              <Col md={6}>
                {/* Column 1: General Information, Heartbeat Information, IoT Jobs */}

                {/* Display General Information */}
                {results.general && (
                  <Card className="mb-3">
                    <Card.Header>General Information</Card.Header>
                    <Card.Body>
                      <p><strong>ICCID:</strong> {results.general.iccid || 'N/A'}</p>
                      <p><strong>Year of Manufacture:</strong> {results.general.year_of_manufacture || 'N/A'}</p>
                      <p><strong>Refurb Records:</strong> {results.general.refurb_records !== undefined ? results.general.refurb_records : 'N/A'}</p>
                      <p><strong>Device Type:</strong> {results.general.device_type || 'N/A'}</p>
                      <p><strong>Battery Replaced:</strong> {results.general.battery_replaced ? 'Yes' : 'No'}</p>
                    </Card.Body>
                  </Card>
                )}

                {/* Display Heartbeat Information */}
                {results.heartbeat && (
                  <Card className="mb-3">
                    <Card.Header>Heartbeat Information</Card.Header>
                    <Card.Body>
                      <p><strong>Last Seen:</strong> {results.heartbeat.last_seen || 'N/A'}</p>
                      <p><strong>Firmware:</strong> {results.heartbeat.firmware || 'N/A'}</p>
                      <p><strong>Battery Percentage:</strong> {results.heartbeat.battery_percentage !== undefined ? results.heartbeat.battery_percentage + '%' : 'N/A'}</p>
                      <p><strong>GPS Status:</strong> {results.heartbeat.gps_status || 'N/A'}</p>
                      <p>
                        <strong>Location:</strong> {results.heartbeat.location || 'N/A'}
                        {results.heartbeat.location_url && results.heartbeat.location !== 'N/A' && (
                          <a href={results.heartbeat.location_url} target="_blank" rel="noopener noreferrer" className="ms-2">
                            View Map
                          </a>
                        )}
                      </p>
                    </Card.Body>
                  </Card>
                )}

                {/* Display IoT Jobs Information */}
                {results.iot && results.iot.jobs && results.iot.jobs.length > 0 && (
                  <Card className="mb-3">
                    <Card.Header>IoT Jobs</Card.Header>
                    <Card.Body>
                      <Table striped bordered hover size="sm">
                        <thead>
                          <tr>
                            <th>Job ID</th>
                            <th>Status</th>
                            <th>Last Updated</th>
                          </tr>
                        </thead>
                        <tbody>
                          {results.iot.jobs.map((job: any, index: number) => (
                            <tr key={index}>
                              <td>{job.jobId || 'N/A'}</td>
                              <td>{job.status || 'N/A'}</td>
                              <td>{job.lastUpdatedAt || 'N/A'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    </Card.Body>
                  </Card>
                )}
              </Col>
              
              <Col md={6}>
                {/* Column 2: Registration Information, Thing Shadow */}

                {/* Display Registration Information */}
                {results.registration && (
                  <Card className="mb-3">
                    <Card.Header>Registration Information</Card.Header>
                    <Card.Body>
                      <p><strong>Account Name:</strong> {results.registration.account_name || 'N/A'}</p>
                      <p><strong>Registration Time:</strong> {results.registration.registration_time || 'N/A'}</p>
                      <p><strong>Firmware on Registration:</strong> {results.registration.firmware_on_registration || 'N/A'}</p>
                      <p><strong>Battery on Registration:</strong> {results.registration.battery_on_registration !== undefined ? results.registration.battery_on_registration + '%' : 'N/A'}</p>
                    </Card.Body>
                  </Card>
                )}

                {/* Display Thing Shadow Information */}
                {results.iot && results.iot.shadow && (
                  <Card className="mb-3">
                    <Card.Header>Thing Shadow</Card.Header>
                    <Card.Body>
                      <ListGroup variant="flush">
                        {Object.entries(results.iot.shadow).map(([key, value]: [string, any], index: number) => {
                          // Define which keys are editable using their DISPLAY names
                          const editableDisplayKeys = ['Debug', 'Trip-Timeout', 'After-Trip-Reports', 'Heartbeat-Interval'];
                          const isEditable = editableDisplayKeys.includes(key);

                          // For 'Debug' and 'After-Trip-Reports', display true/false. Other editable values as is.
                          const displayValue = isEditable
                            ? (key === 'Debug' || key === 'After-Trip-Reports'
                                ? editableShadow[key] === true ? 'True' : 'False'
                                : editableShadow[key] !== undefined ? editableShadow[key] : ''
                              )
                            : String(value); // Use String(value) for non-editable to avoid [object Object]

                          return (
                            <ListGroup.Item key={key} className="d-flex justify-content-between align-items-center">
                              <strong>{key}:</strong>
                              {isEditable ? (
                                key === 'Debug' || key === 'After-Trip-Reports' ? (
                                  <Form.Check
                                    type="checkbox"
                                    checked={editableShadow[key] === true}
                                    onChange={(e) => handleChangeShadowField(key, e.target.checked)}
                                    className="ms-2"
                                    disabled={isUpdatingShadow}
                                  />
                                ) : (
                                  <Form.Control
                                    type="number" // Assuming 'Trip-Timeout' and 'Heartbeat-Interval' are numbers
                                    value={editableShadow[key] !== undefined ? editableShadow[key] : ''}
                                    onChange={(e) => handleChangeShadowField(key, e.target.value)}
                                    className="ms-2 w-50"
                                    disabled={isUpdatingShadow}
                                  />
                                )
                              ) : (
                                <span className="ms-2">{String(value)}</span> // Use String(value) for non-editable to avoid [object Object]
                              )}
                            </ListGroup.Item>
                          );
                        })}
                      </ListGroup>
                      {/* Update Shadow Button */}
                      <Button
                        variant="success"
                        className="mt-3"
                        onClick={handleUpdateShadow}
                        disabled={isUpdatingShadow || isLoading}
                      >
                        {isUpdatingShadow ? <Spinner animation="border" size="sm" className="me-2" /> : null}
                        Update Shadow
                      </Button>
                      {isUpdatingShadow && <span className="ms-2">Updating...</span>}
                    </Card.Body>
                  </Card>
                )}
              </Col>
            </Row>

          </Card.Body>
        </Card>
      )}
    </Container>
  );
}