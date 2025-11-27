import React, { useState, useEffect } from 'react';
import { Container, Form, Button, Row, Col, Card, Alert, Spinner, ListGroup } from 'react-bootstrap';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

// --- TypeScript Interfaces for the API response ---
interface AccountInfo {
  id: string;
  name: string;
}

interface CognitoUserInfo {
  username: string;
  status: string;
  enabled: boolean;
  attributes: { [key: string]: string };
}

interface PersonLookupResult {
  person_id: string;
  account: AccountInfo | null;
  cognito_user: CognitoUserInfo | null;
  errors: string[];
  error?: string;
}

// --- Sub-components for rendering results ---

const AccountInfoCard: React.FC<{ account: AccountInfo }> = ({ account }) => (
  <Card className="mb-3">
    <Card.Header><h5>🏢 Account Information</h5></Card.Header>
    <ListGroup variant="flush">
      <ListGroup.Item><strong>Account Name:</strong> {account.name}</ListGroup.Item>
      <ListGroup.Item><strong>Account ID:</strong> {account.id}</ListGroup.Item>
    </ListGroup>
  </Card>
);

const CognitoUserCard: React.FC<{ user: CognitoUserInfo, personId: string }> = ({ user, personId }) => {
  const [isEnabled, setIsEnabled] = useState(user.enabled);
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);

  useEffect(() => {
    setIsEnabled(user.enabled);
  }, [user.enabled]);

  const handleEnabledChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEnabledState = e.target.checked;
    const action = newEnabledState ? "enable" : "disable";

    // Show confirmation dialog before making any changes
    if (window.confirm(`Are you sure you want to ${action} this user?`)) {
      setIsUpdating(true);
      setUpdateError(null);
      setIsEnabled(newEnabledState); // Optimistic UI update

      try {
        await axios.post(`${API_BASE_URL}/api/set_person_enabled_status`, {
          person_id: personId,
          enabled: newEnabledState,
        });
        // Success, state is already updated
      } catch (err: any) {
        setIsEnabled(!newEnabledState); // Revert on error
        setUpdateError(err.response?.data?.detail || "Failed to update user status.");
      } finally {
        setIsUpdating(false);
      }
    }
    // If user cancels, do nothing. The switch's state is bound to `isEnabled`, 
    // which hasn't been changed, so it will visually remain in its original position.
  };

  return (
    <Card className="mb-3">
      <Card.Header><h5>👤 Cognito User Details</h5></Card.Header>
      <ListGroup variant="flush">
        <ListGroup.Item><strong>Username:</strong> {user.username}</ListGroup.Item>
        <ListGroup.Item><strong>Status:</strong> {user.status}</ListGroup.Item>
        <ListGroup.Item className="d-flex justify-content-between align-items-center">
          <strong>Enabled:</strong>
          <Form.Check
            type="switch"
            checked={isEnabled}
            onChange={handleEnabledChange}
            disabled={isUpdating}
            label={isUpdating ? "Updating..." : ""}
          />
        </ListGroup.Item>
        {user.attributes && Object.keys(user.attributes).length > 0 && (
          <ListGroup.Item>
            <strong>Attributes:</strong>
            <ul className="list-unstyled ms-3 mb-0">
              {Object.entries(user.attributes).map(([key, value]) => (
                <li key={key}><strong>{key}:</strong> {value}</li>
              ))}
            </ul>
          </ListGroup.Item>
        )}
      </ListGroup>
      {updateError && <Card.Footer><Alert variant="danger" className="mb-0">{updateError}</Alert></Card.Footer>}
    </Card>
  );
};


export function PersonDetailsPage() {
  const [personId, setPersonId] = useState<string>('');
  const [personLookupResult, setPersonLookupResult] = useState<PersonLookupResult | null>(null);
  const [isLoadingPerson, setIsLoadingPerson] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handlePersonLookup = async () => {
    setError(null);
    setPersonLookupResult(null);
    setIsLoadingPerson(true);
    try {
      const response = await axios.get<PersonLookupResult>(`${API_BASE_URL}/api/person_lookup`, {
        params: { person_id: personId }
      });
      setPersonLookupResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to perform person lookup.');
    } finally {
      setIsLoadingPerson(false);
    }
  };

  return (
    <Container className="mt-4">
      <h1>Person Details</h1>

      {error && <Alert variant="danger" className="mt-3">{error}</Alert>}

      <Row className="mt-4">
        <Col md={12}>
          <Card>
            <Card.Header>
              <h5>Person ID Lookup</h5>
            </Card.Header>
            <Card.Body>
              <Form.Group className="mb-3">
                <Form.Label>Person ID (UUID)</Form.Label>
                <Form.Control
                  type="text"
                  placeholder="Enter Person ID (e.g., xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
                  value={personId}
                  onChange={(e) => setPersonId(e.target.value)}
                />
              </Form.Group>
              <Button onClick={handlePersonLookup} disabled={isLoadingPerson || !personId}>
                {isLoadingPerson ? <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> : 'Lookup Person'}
              </Button>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {personLookupResult && (
        <div className="mt-4">
          {personLookupResult.error && <Alert variant="danger">{personLookupResult.error}</Alert>}
          {personLookupResult.errors && personLookupResult.errors.length > 0 && (
            <Alert variant="warning">
              <Alert.Heading>Encountered {personLookupResult.errors.length} issues:</Alert.Heading>
              <ul>
                {personLookupResult.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </Alert>
          )}

          <Row>
            <Col md={8}>
              {personLookupResult.account && <AccountInfoCard account={personLookupResult.account} />}
              {personLookupResult.cognito_user && <CognitoUserCard user={personLookupResult.cognito_user} personId={personId} />}
            </Col>
          </Row>
        </div>
      )}
    </Container>
  );
}
