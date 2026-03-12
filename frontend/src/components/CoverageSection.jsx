import SectionTable from './SectionTable.jsx'

export default function CoverageSection({ data, p1name, p2name }) {
  return (
    <SectionTable
      title="Coverage"
      icon="🛡️"
      data={data}
      p1name={p1name}
      p2name={p2name}
      colorClass="coverage"
    />
  )
}
