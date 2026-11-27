import test from 'node:test';
import assert from 'node:assert/strict';
import { appSection, primaryDestination, unreadCount, reactionSummary, notificationPresentation, persistReaction, winDraft } from './socialModel.mjs';
const session = { id: 'member-1', active_session_id: 'login-A' };

test('complete app navigation preserves each legacy destination under a primary section', () => {
  for (const tab of ['bot-BTC','bot-ETH','bot-SOL','bot-XRP','bot-DOGE','stocks','portfolio','practice','favorites']) assert.equal(appSection(tab), 'trading');
  assert.equal(appSection('chat'), 'community'); assert.equal(appSection('members'), 'community');
  for (const tab of ['notifications','achievements','profile']) assert.equal(appSection(tab), tab);
  assert.equal(primaryDestination('trading','stocks'),'stocks');
  assert.equal(primaryDestination('trading','unknown'),'bot-BTC');
  assert.equal(primaryDestination('community'),'chat');
});

test('only persisted unread notifications contribute to the badge and mentions have a complete label', () => {
  assert.equal(unreadCount([{id:'a',read:false},{id:'b',read:true},{type:'reaction'}]),1);
  assert.equal(notificationPresentation({type:'mention',data:{mentioner_name:'Jamie'}}).title,'Jamie mentioned you');
  assert.equal(notificationPresentation({type:'reaction',data:{reactor_name:'Jamie',reaction_type:'rocket'}}).icon,'🚀');
});

test('sharing a win opens a clearly editable draft and preserves an existing message', () => {
  assert.match(winDraft(''),/self-reported/);
  assert.match(winDraft(''),/What I learned/);
  assert.equal(winDraft('An unfinished question'), 'An unfinished question');
});

test('reaction summaries normalize old emoji aliases without double counting the same member', () => {
  const result=reactionSummary({heart:[{user_id:'member-1'}],'❤️':[{user_id:'member-1'},{user_id:'member-2'}],rocket:[{user_id:'member-3'}]},session.id);
  assert.deepEqual(result.counts,{'❤️':2,'🚀':1}); assert.deepEqual(result.mine,['heart']);
});

test('reaction writes use the captured identity and hydrate counts from the server', async () => {
  const requests=[];
  const client={post:async (...args)=>requests.push(args),get:async (...args)=>{requests.push(args);return{data:{money:[{user_id:session.id}]}};}};
  const result=await persistReaction({client,api:'/api',session,currentSession:()=>session,messageId:'message/one',reaction:'💰'});
  assert.equal(requests[0][0],'/api/messages/message%2Fone/react');
  assert.deepEqual(requests[0][1],{user_id:'member-1',reaction_type:'money'});
  assert.equal(requests[0][2].headers['X-Session-ID'],'login-A');
  assert.deepEqual(result.counts,{'💰':1});
});

test('late completion after a new login cannot hydrate the new account with the old reaction', async () => {
  let active=session;let reads=0;
  const client={post:async()=>{active={...session,active_session_id:'login-B'};},get:async()=>{reads++;return{data:{}};}};
  const result=await persistReaction({client,api:'/api',session,currentSession:()=>active,messageId:'m',reaction:'heart'});
  assert.equal(result,null);assert.equal(reads,0);
});

test('another tab duplicate reloads the real counts, while a failed write never fabricates a count', async () => {
  const duplicate={response:{status:400,data:{detail:'Already reacted to this message'}}};
  const client={post:async()=>{throw duplicate;},get:async()=>({data:{heart:[{user_id:session.id}]}})};
  const args={client,api:'/api',session,currentSession:()=>session,messageId:'m',reaction:'heart'};
  assert.deepEqual((await persistReaction(args)).counts,{'❤️':1});
  client.post=async()=>{throw new Error('offline');};
  await assert.rejects(persistReaction(args),/offline/);
});

 test('removing a reaction uses the same captured session and canonical wire value', async () => {
  const requests=[];
  const client={delete:async(...args)=>requests.push(args),get:async()=>({data:{}})};
  await persistReaction({client,api:'/api',session,currentSession:()=>session,messageId:'m',reaction:'👍',remove:true});
  assert.deepEqual(requests[0][1].params,{user_id:'member-1',reaction_type:'thumbs_up'});
  assert.equal(requests[0][1].headers['X-Session-ID'],'login-A');
});
