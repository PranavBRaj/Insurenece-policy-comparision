import SectionTable from './SectionTable.jsx'

export default function ExclusionsSection({ data, p1name, p2name }) {
  return (
    <SectionTable
      title="Exclusions"
      icon="🚫"
      data={data}
      p1name={p1name}
      p2name={p2name}
      colorClass="exclusions"
    />
  )
}
