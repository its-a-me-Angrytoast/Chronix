import React from 'react';
import { motion } from 'framer-motion';
import './StatCard.css';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color }) => {
  return (
    <motion.div 
      whileHover={{ y: -5, scale: 1.02 }}
      className="stat-card"
      style={{ '--accent-color': color } as React.CSSProperties}
    >
      <div className="stat-header">
        {/* Icon is now decorative background element or minimal top indicator */}
        <div className="stat-icon-mini" style={{ color: color }}>{icon}</div>
      </div>
      
      <div className="stat-content">
        <h3 className="stat-value">{value}</h3>
        <p className="stat-label">{title}</p>
      </div>
    </motion.div>
  );
};

export default StatCard;