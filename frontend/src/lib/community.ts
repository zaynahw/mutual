import type { AvailabilityCard } from './api';
import { getBlockPosition } from '../components/scheduleTime.js';

export type ConnectionKind = 'friend'|'community'|'own';
export function connectionKind(card:AvailabilityCard,userId:string,friends:Set<string>):ConnectionKind {
  return card.owner.id===userId?'own':friends.has(card.owner.id)?'friend':'community';
}
export function layoutCommunityDay(cards:AvailabilityCard[],dayKey:string,timezone:string) {
  const items=cards.map(card=>({card,position:getBlockPosition(card.window.start,card.window.end,dayKey,timezone)}))
    .filter((item):item is {card:AvailabilityCard;position:{top:number;height:number}}=>item.position!==null)
    .sort((a,b)=>a.position.top-b.position.top||a.position.height-b.position.height||a.card.window.id.localeCompare(b.card.window.id));
  const result:(typeof items[number]&{lane:number;lanes:number})[]=[];
  let group:(typeof result[number])[]=[];let laneEnds:number[]=[];let groupEnd=-1;
  function finish(){for(const item of group){item.lanes=laneEnds.length;result.push(item);}group=[];laneEnds=[];}
  for(const item of items){
    const end=item.position.top+item.position.height;
    if(item.position.top>=groupEnd){finish();groupEnd=-1;}
    let lane=laneEnds.findIndex(value=>value<=item.position.top);
    if(lane===-1)lane=laneEnds.length;
    laneEnds[lane]=end;groupEnd=Math.max(groupEnd,end);
    group.push({...item,lane,lanes:1});
  }
  finish();return result;
}
