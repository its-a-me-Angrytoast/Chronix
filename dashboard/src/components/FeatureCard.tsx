import React from 'react';

const FeatureCard = ({ title, description, icon }: { title: string, description: string, icon: React.ReactNode }) => {
  return (
    <div className="feature-card">
      <div className="feature-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
};

export default FeatureCard;
