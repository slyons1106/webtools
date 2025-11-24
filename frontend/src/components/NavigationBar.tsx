import React from 'react';
import { Navbar, Container, Nav } from 'react-bootstrap';
import { Link } from 'react-router-dom';

export function NavigationBar() {
  return (
    <Navbar bg="dark" variant="dark" expand="lg">
      <Container>
        <Navbar.Brand as={Link} to="/person-details">WebTools</Navbar.Brand>
        <Navbar.Toggle aria-controls="basic-navbar-nav" />
        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto">
            <Nav.Link as={Link} to="/person-details">Person Lookup</Nav.Link>
            <Nav.Link as={Link} to="/iccid-lookup">ICCID Lookup</Nav.Link>
            <Nav.Link as={Link} to="/labels">Labels</Nav.Link>

            <Nav.Link as={Link} to="/log-search">API Log Search</Nav.Link>
            <Nav.Link as={Link} to="/s3-viewer">S3 Label Viewer</Nav.Link>
            <Nav.Link as={Link} to="/csv-splitter">CSV Splitter</Nav.Link>
            <Nav.Link as={Link} to="/tools">Tools</Nav.Link>
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
}
