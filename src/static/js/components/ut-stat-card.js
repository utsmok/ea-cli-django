/**
 * UT Stat Card Web Component
 *
 * Usage:
 *   <ut-stat-card value="1,234" label="Total Items"></ut-stat-card>
 *   <ut-stat-card value="456" label="Completed" color="success"></ut-stat-card>
 *   <ut-stat-card value="12" label="Failed" color="error" trend="down"></ut-stat-card>
 *
 * Attributes:
 *   value: The stat value to display
 *   label: The stat label
 *   color: Color variant (default, primary, success, warning, error)
 *   trend: Optional trend indicator (up, down, neutral)
 *   icon: Optional icon SVG
 */

class UTStatCard extends HTMLElement {
  static observedAttributes = ['value', 'label', 'color', 'trend', 'icon'];

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.render();
  }

  attributeChangedCallback() {
    this.render();
  }

  get value() {
    return this.getAttribute('value') || '0';
  }

  get label() {
    return this.getAttribute('label') || 'Stat';
  }

  get color() {
    return this.getAttribute('color') || 'primary';
  }

  get trend() {
    return this.getAttribute('trend') || '';
  }

  get icon() {
    return this.getAttribute('icon') || '';
  }

  getColor() {
    const colors = {
      'default': 'var(--ut-grey-02)',
      'primary': 'var(--ut-blue)',
      'success': 'var(--ut-darkgreen)',
      'warning': 'var(--ut-red)',
      'error': 'var(--ut-darkred)',
      'info': 'var(--ut-purple)',
    };
    return colors[this.color] || colors['primary'];
  }

  getBorderColor() {
    return this.getColor();
  }

  getTrendIcon() {
    const trend = this.trend.toLowerCase();
    if (trend === 'up') {
      return `<svg class="trend-icon trend-up" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 12L4 8h3V4h2v4h3z"/>
      </svg>`;
    } else if (trend === 'down') {
      return `<svg class="trend-icon trend-down" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 4l4 4H9v4H7V8H4z"/>
      </svg>`;
    }
    return '';
  }

  getStyles() {
    return `
      <style>
        @import url('/static/css/ut-brand.css');

        :host {
          display: block;
        }

        .stat-card {
          background: var(--ut-white);
          border: 1px solid var(--ut-grey-04);
          border-top: 4px solid ${this.getBorderColor()};
          padding: 1.5rem;
          text-align: center;
          transition: all 0.2s ease;
          cursor: pointer;
          position: relative;
          overflow: hidden;
        }

        .stat-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        .stat-card::before {
          content: '';
          position: absolute;
          top: 0;
          left: -100%;
          width: 100%;
          height: 100%;
          background: linear-gradient(
            90deg,
            transparent,
            rgba(255, 255, 255, 0.5),
            transparent
          );
          transition: left 0.5s ease;
        }

        .stat-card:hover::before {
          left: 100%;
        }

        .stat-icon {
          margin-bottom: 0.75rem;
          color: ${this.getColor()};
        }

        .stat-icon svg {
          width: 32px;
          height: 32px;
        }

        .stat-value {
          font-family: 'Arial Narrow', Arial, sans-serif;
          font-size: 2.5rem;
          font-weight: 700;
          color: ${this.getColor()};
          line-height: 1;
          margin-bottom: 0.5rem;
        }

        .stat-label {
          font-family: 'Arial', sans-serif;
          font-size: 0.875rem;
          color: var(--ut-grey-02);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.375rem;
        }

        .trend-icon {
          font-size: 0.75rem;
        }

        .trend-up {
          color: var(--ut-darkgreen);
        }

        .trend-down {
          color: var(--ut-darkred);
        }
      </style>
    `;
  }

  render() {
    const iconHtml = this.icon ? `<div class="stat-icon">${this.icon}</div>` : '';
    const trendHtml = this.getTrendIcon();

    this.shadowRoot.innerHTML = `
      ${this.getStyles()}
      <div class="stat-card">
        ${iconHtml}
        <div class="stat-value">${this.value}</div>
        <div class="stat-label">
          ${this.label}
          ${trendHtml}
        </div>
      </div>
    `;
  }
}

customElements.define('ut-stat-card', UTStatCard);

export default UTStatCard;
