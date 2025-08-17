import React from 'react';
import { Container, Typography, Box } from '@mui/material';

const Dashboard: React.FC = () => {
  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          LinkedIn Automation Dashboard
        </Typography>
        <Typography variant="body1">
          Welcome to your LinkedIn job application automation system. This dashboard will show your application statistics, recent jobs, and automation status.
        </Typography>
      </Box>
    </Container>
  );
};

export default Dashboard;